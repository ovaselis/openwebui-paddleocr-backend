import asyncio
import logging
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class PaddleOCREngine:
    name = "paddleocr"

    def __init__(self) -> None:
        self._ocr: Any | None = None

    def _get_ocr(self) -> Any:
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install PaddleOCR and PaddlePaddle first."
                ) from exc

            logger.info(
                "Loading PaddleOCR model with lang=%s on GPU",
                settings.ocr_lang,
            )

            self._ocr = PaddleOCR(
                lang=settings.ocr_lang,
                device="gpu:0",

                # Laptop-friendly models for 8 GB VRAM.
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="latin_PP-OCRv5_mobile_rec",

                # Disable extra preprocessing for MVP.
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )

        return self._ocr

    async def extract_text(self, image_path: Path) -> tuple[str, float | None]:
        return await asyncio.to_thread(self._extract_text_sync, image_path)

    def _extract_text_sync(self, image_path: Path) -> tuple[str, float | None]:
        ocr = self._get_ocr()
        result = ocr.predict(
    		str(image_path),
    		text_det_limit_side_len=1280,
    		text_det_limit_type="min",
    		text_det_thresh=0.2,
    		text_det_box_thresh=0.3,
    		text_det_unclip_ratio=1.8,
	)

        logger.info("Raw PaddleOCR result type: %s", type(result))
        logger.info("Raw PaddleOCR result repr: %r", result)

        texts: list[str] = []
        scores: list[float] = []

        for item in result:
            data = self._extract_result_dict(item)

            logger.info("Parsed PaddleOCR item keys: %s", list(data.keys()))
            logger.info("Parsed PaddleOCR item data: %r", data)

            found_texts = self._find_values_by_key(data, {"rec_texts", "texts"})
            found_scores = self._find_values_by_key(data, {"rec_scores", "scores"})

            for value in found_texts:
                if isinstance(value, list):
                    for text_item in value:
                        text = str(text_item).strip()
                        if text:
                            texts.append(text)
                elif isinstance(value, str) and value.strip():
                    texts.append(value.strip())

            for value in found_scores:
                if isinstance(value, list):
                    for score_item in value:
                        try:
                            scores.append(float(score_item))
                        except (TypeError, ValueError):
                            pass
                else:
                    try:
                        scores.append(float(value))
                    except (TypeError, ValueError):
                        pass

        text = "\n".join(texts).strip()
        confidence = sum(scores) / len(scores) if scores else None

        logger.info("Extracted OCR text: %r", text)
        logger.info("Extracted OCR confidence: %r", confidence)

        return text, confidence

    @staticmethod
    def _extract_result_dict(item: Any) -> dict[str, Any]:
        """Handle PaddleOCR 3.x result objects and dict-like outputs."""
        if isinstance(item, dict):
            return item

        res = getattr(item, "res", None)
        if isinstance(res, dict):
            return {"res": res}

        json_method = getattr(item, "json", None)
        if callable(json_method):
            try:
                data = json_method()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        to_dict = getattr(item, "to_dict", None)
        if callable(to_dict):
            try:
                data = to_dict()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        try:
            return dict(item)
        except Exception:
            logger.warning("Could not parse PaddleOCR result object: %r", item)
            return {}

    @staticmethod
    def _find_values_by_key(data: Any, keys: set[str]) -> list[Any]:
        """Recursively find values for matching keys inside nested OCR output."""
        found: list[Any] = []

        if isinstance(data, dict):
            for key, value in data.items():
                if key in keys:
                    found.append(value)
                found.extend(PaddleOCREngine._find_values_by_key(value, keys))

        elif isinstance(data, list):
            for item in data:
                found.extend(PaddleOCREngine._find_values_by_key(item, keys))

        return found