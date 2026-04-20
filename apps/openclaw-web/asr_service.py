"""
ASR Service — 音频转写（faster-whisper v1.2+）
transcribe_audio(file_path, language="zh")
"""
import tempfile, os

def transcribe_audio(file_path: str, language: str = "zh") -> str:
    """用 faster-whisper 将音频文件转写为文字"""
    try:
        import faster_whisper
    except ImportError as e:
        return f"[ASR错误] faster-whisper 未安装: {e}"
    except Exception as e:
        return f"[ASR错误] 导入失败: {e}"

    try:
        model = faster_whisper.WhisperModel(
            model_size_or_path="base",
            device="cpu",
            local_files_only=False
        )
        segments, info = model.transcribe(file_path, beam_size=3, language=language if language else None)
        transcript = "".join(seg.text for seg in segments if seg.text.strip())
        if not transcript.strip():
            return "[ASR错误] 未能识别语音内容"
        return transcript.strip()
    except Exception as e:
        return f"[ASR错误: {e}]"
