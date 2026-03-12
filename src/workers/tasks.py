from __future__ import annotations

import asyncio
from typing import Optional

from src.core.projects import ProjectManager
from src.core.statuses import format_status_message
from src.integrations.notebooklm.adapter import NotebookLMAdapter, detect_intent
from src.models.material import MaterialStatus, MaterialType, ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject
from src.models.result import ResearchResult
from src.utils.converters import is_format_supported, suggest_conversion
from src.utils.logging import logger
from src.workers.retries import retry_with_backoff


class ResearchTaskProcessor:
    """Processes a research project end-to-end: upload materials, generate, deliver."""

    def __init__(
        self,
        project_manager: Optional[ProjectManager] = None,
        adapter: Optional[NotebookLMAdapter] = None,
    ):
        self.project_manager = project_manager or ProjectManager()
        self.adapter = adapter or NotebookLMAdapter()

    async def process_project(
        self,
        project: ResearchProject,
        status_callback=None,
    ) -> Optional[ResearchResult]:
        """Full pipeline: prepare -> upload -> generate -> return result.

        status_callback: async function(project_id, status, project_name)
            called at each status transition so the Telegram handler can
            send status updates.
        """
        project_id = project.project_id

        async def notify(status: ProjectStatus):
            self.project_manager.update_status(project_id, status)
            if status_callback:
                await status_callback(
                    project_id, status, project.project_name
                )

        try:
            # Phase 1: Materials preparing
            await notify(ProjectStatus.MATERIALS_PREPARING)
            materials = self.project_manager.get_materials(project_id)

            if not self.adapter.is_available:
                logger.warning("NotebookLM not available, skipping processing")
                await notify(ProjectStatus.ERROR)
                return None

            # Create NotebookLM notebook
            notebook_id = await retry_with_backoff(
                self.adapter.create_project, project.project_name
            )
            if not notebook_id:
                await notify(ProjectStatus.ERROR)
                return None

            self.project_manager.project_repo.update(
                project_id, {"notebooklm_project_id": notebook_id}
            )

            # Upload materials
            upload_errors = []
            for material in materials:
                if not is_format_supported(material.material_type):
                    hint = suggest_conversion(material.material_type)
                    upload_errors.append(
                        f"{material.display_name}: unsupported format. {hint or ''}"
                    )
                    self.project_manager.update_material_status(
                        material.material_id, MaterialStatus.ERROR
                    )
                    continue

                self.project_manager.update_material_status(
                    material.material_id, MaterialStatus.UPLOADING
                )
                try:
                    success = await retry_with_backoff(
                        self.adapter.upload_material, notebook_id, material
                    )
                    if success:
                        self.project_manager.update_material_status(
                            material.material_id, MaterialStatus.ADDED_TO_NOTEBOOKLM
                        )
                    else:
                        self.project_manager.update_material_status(
                            material.material_id, MaterialStatus.ERROR
                        )
                        upload_errors.append(
                            f"{material.display_name}: upload failed"
                        )
                except Exception as e:
                    self.project_manager.update_material_status(
                        material.material_id, MaterialStatus.ERROR
                    )
                    upload_errors.append(f"{material.display_name}: {e}")

            # Phase 2: Sent to NotebookLM
            await notify(ProjectStatus.SENT_TO_NOTEBOOKLM)

            # Phase 3: Generating
            await notify(ProjectStatus.GENERATING)

            action = detect_intent(project.original_user_request)
            result = await retry_with_backoff(
                self.adapter.generate_result, notebook_id, action
            )

            if result is None:
                await notify(ProjectStatus.ERROR)
                return None

            # Mark materials as used
            for material in materials:
                if material.status != MaterialStatus.ERROR:
                    self.project_manager.update_material_status(
                        material.material_id, MaterialStatus.USED_IN_RESULT
                    )

            # Phase 4: Completed
            self.project_manager.update_result(
                project_id,
                result_type=result.result_type,
                result_ref=result.notebooklm_ref,
                result_summary=result.content[:500] if result.content else None,
            )
            await notify(ProjectStatus.COMPLETED)

            if upload_errors:
                result.metadata["upload_errors"] = upload_errors

            return result

        except Exception as e:
            logger.error(f"Failed to process project {project_id}: {e}")
            await notify(ProjectStatus.ERROR)
            return None
