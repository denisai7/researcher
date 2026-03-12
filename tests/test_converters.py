from src.models.material import MaterialType
from src.utils.converters import (
    classify_text_content,
    detect_material_type_from_extension,
    extract_urls,
    is_format_supported,
    is_url,
    is_youtube_url,
)


class TestYouTubeDetection:
    def test_standard_youtube(self):
        assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_short_youtube(self):
        assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ")

    def test_shorts_youtube(self):
        assert is_youtube_url("https://www.youtube.com/shorts/abc123")

    def test_not_youtube(self):
        assert not is_youtube_url("https://example.com/video")


class TestURLDetection:
    def test_valid_url(self):
        assert is_url("https://example.com")
        assert is_url("http://example.com/path?q=1")

    def test_invalid_url(self):
        assert not is_url("not a url")
        assert not is_url("ftp://something")


class TestClassifyTextContent:
    def test_youtube_url(self):
        assert (
            classify_text_content("https://youtube.com/watch?v=abc")
            == MaterialType.YOUTUBE
        )

    def test_regular_url(self):
        assert classify_text_content("https://example.com/article") == MaterialType.LINK

    def test_plain_text(self):
        assert classify_text_content("make a summary of this") is None


class TestExtractURLs:
    def test_extract_single(self):
        urls = extract_urls("Check out https://example.com for more info")
        assert urls == ["https://example.com"]

    def test_extract_multiple(self):
        urls = extract_urls("See https://a.com and https://b.com")
        assert len(urls) == 2

    def test_no_urls(self):
        assert extract_urls("No URLs here") == []


class TestMaterialTypeDetection:
    def test_pdf(self):
        assert detect_material_type_from_extension("doc.pdf") == MaterialType.PDF

    def test_audio(self):
        assert detect_material_type_from_extension("song.mp3") == MaterialType.AUDIO
        assert detect_material_type_from_extension("voice.ogg") == MaterialType.AUDIO

    def test_video(self):
        assert detect_material_type_from_extension("clip.mp4") == MaterialType.VIDEO

    def test_image(self):
        assert detect_material_type_from_extension("photo.jpg") == MaterialType.IMAGE
        assert detect_material_type_from_extension("pic.png") == MaterialType.IMAGE

    def test_unknown(self):
        assert detect_material_type_from_extension("data.xyz") == MaterialType.FILE


class TestFormatSupport:
    def test_supported(self):
        assert is_format_supported(MaterialType.PDF)
        assert is_format_supported(MaterialType.LINK)
        assert is_format_supported(MaterialType.YOUTUBE)
        assert is_format_supported(MaterialType.AUDIO)

    def test_unsupported(self):
        assert not is_format_supported(MaterialType.IMAGE)
        assert not is_format_supported(MaterialType.VIDEO)
