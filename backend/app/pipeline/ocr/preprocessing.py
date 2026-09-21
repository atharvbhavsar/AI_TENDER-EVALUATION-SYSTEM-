"""Robust image preprocessing module for document OCR using OpenCV, Pillow, and adaptive quality profiling."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger("app.pipeline.ocr.preprocessing")


@dataclass
class ImageQualityProfile:
    """Pre-OCR document image quality profile for adaptive preprocessing decisions."""

    orientation: int = 0  # 0, 90, 180, 270 degrees
    rotation_required: bool = False
    skew_angle: float = 0.0  # Estimated skew in degrees
    brightness_score: float = 0.5  # Mean brightness normalized to [0.0, 1.0]
    contrast_score: float = 0.5  # Standard deviation contrast normalized to [0.0, 1.0]
    sharpness_score: float = 0.5  # Laplacian variance normalized to [0.0, 1.0]
    noise_score: float = 0.0  # High-frequency noise level [0.0, 1.0]
    resolution_width: int = 0
    resolution_height: int = 0
    is_low_quality: bool = False


@dataclass
class PreprocessingResult:
    """Container for processed image, applied transforms, and diagnostic metrics."""

    image: np.ndarray  # Processed image (grayscale or BGR)
    skew_angle: float = 0.0  # Estimated skew angle in degrees
    orientation_angle: int = 0  # 0, 90, 180, or 270
    is_upscaled: bool = False
    scale_factor: float = 1.0
    variant_name: str = "standard"
    applied_transforms: List[str] = field(default_factory=list)
    quality_profile: Optional[ImageQualityProfile] = None


class ImagePreprocessor:
    """Industrial document image preprocessing engine for PaddleOCR and document understanding."""

    MIN_TARGET_DIMENSION: int = 1200
    MAX_SAFE_DIMENSION: int = 3500

    @classmethod
    def pil_to_cv2(cls, pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV BGR numpy array."""
        if pil_image.mode == "RGBA":
            bg = Image.new("RGB", pil_image.size, (255, 255, 255))
            bg.paste(pil_image, mask=pil_image.split()[3])
            pil_image = bg
        elif pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        arr = np.array(pil_image)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    @classmethod
    def cv2_to_pil(cls, cv2_image: np.ndarray) -> Image.Image:
        """Convert OpenCV numpy array to PIL Image."""
        if len(cv2_image.shape) == 2:
            return Image.fromarray(cv2_image)
        rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @classmethod
    def handle_resolution(cls, img: np.ndarray) -> Tuple[np.ndarray, bool, float]:
        """Detect low-resolution images and upscale cleanly using bicubic interpolation.
        
        Constrains dimensions to avoid unbounded memory usage.
        """
        h, w = img.shape[:2]
        min_dim = min(h, w)
        max_dim = max(h, w)

        if max_dim > cls.MAX_SAFE_DIMENSION:
            scale = cls.MAX_SAFE_DIMENSION / float(max_dim)
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            return resized, True, scale

        if min_dim < cls.MIN_TARGET_DIMENSION:
            scale = min(2.0, cls.MIN_TARGET_DIMENSION / float(min_dim))
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            return resized, True, scale

        return img, False, 1.0

    @classmethod
    def to_grayscale(cls, img: np.ndarray) -> np.ndarray:
        """Convert BGR image to single-channel 8-bit grayscale."""
        if len(img.shape) == 2:
            return img
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    @classmethod
    def enhance_contrast_clahe(
        cls, gray: np.ndarray, clip_limit: float = 2.5, tile_grid_size: Tuple[int, int] = (8, 8)
    ) -> np.ndarray:
        """Apply Contrast Limited Adaptive Histogram Equalization (CLAHE)."""
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        return clahe.apply(gray)

    @classmethod
    def denoise_image(cls, gray: np.ndarray) -> np.ndarray:
        """Apply edge-preserving bilateral filter to remove noise without blurring characters."""
        return cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)

    @classmethod
    def remove_shadows_and_uneven_lighting(cls, gray: np.ndarray) -> np.ndarray:
        """Reduce uneven illumination and camera shadows using morphological background division."""
        if np.std(gray) < 2.0:
            return gray
        kernel_size = 25
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        normalized = cv2.divide(gray, background, scale=255)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        return clahe.apply(normalized)

    @classmethod
    def estimate_skew_angle(cls, gray: np.ndarray, max_angle: float = 15.0) -> float:
        """Estimate document skew angle in degrees within [-max_angle, +max_angle]."""
        h, w = gray.shape[:2]
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        angles = []
        for c in contours:
            if cv2.contourArea(c) < 150:
                continue
            rect = cv2.minAreaRect(c)
            angle = rect[-1]
            rw, rh = rect[1]
            if rw < rh:
                actual_angle = angle - 90.0
            else:
                actual_angle = angle

            if abs(actual_angle) <= max_angle and abs(actual_angle) > 0.3:
                angles.append(actual_angle)

        if not angles:
            return 0.0

        median_angle = float(np.median(angles))
        return median_angle if abs(median_angle) >= 0.35 else 0.0

    @classmethod
    def deskew_image(cls, gray: np.ndarray, max_angle: float = 15.0) -> Tuple[np.ndarray, float]:
        """Detect and correct document skew within [-max_angle, +max_angle] degrees."""
        h, w = gray.shape[:2]
        median_angle = cls.estimate_skew_angle(gray, max_angle=max_angle)
        if abs(median_angle) < 0.35:
            return gray, 0.0

        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        deskewed = cv2.warpAffine(
            gray,
            rot_mat,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        return deskewed, median_angle

    @classmethod
    def detect_orientation_angle(cls, gray: np.ndarray) -> int:
        """Detect document orientation in degrees (0, 90, 180, 270) using OSD or gradient distribution."""
        # 1. High-accuracy Tesseract OSD if available
        try:
            import pytesseract
            pil_img = Image.fromarray(gray)
            osd = pytesseract.image_to_osd(pil_img, output_type=pytesseract.Output.DICT)
            orient = int(osd.get("orientation", 0))
            conf = float(osd.get("orientation_conf", 0.0))
            if conf >= 1.0 and orient in (0, 90, 180, 270):
                return orient
        except Exception as exc:
            logger.debug("Tesseract OSD not available or skipped: %s", exc)

        # 2. Heuristic fallback: aspect ratio + gradient energy
        h, w = gray.shape[:2]
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mean_gx = np.mean(np.abs(sobel_x))
        mean_gy = np.mean(np.abs(sobel_y))

        if mean_gx > 1.8 * mean_gy and h > w:
            return 90

        return 0

    @classmethod
    def detect_and_correct_orientation(
        cls, img: np.ndarray, angle: Optional[int] = None
    ) -> Tuple[np.ndarray, int]:
        """Detect and orthogonally rotate document to upright orientation (0, 90, 180, 270)."""
        gray = cls.to_grayscale(img)
        detected_angle = angle if angle is not None else cls.detect_orientation_angle(gray)

        if detected_angle == 90:
            # 90° clockwise scan requires 90° counter-clockwise (or 270° clockwise) rotation to restore
            corrected = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            return corrected, 90
        elif detected_angle == 180:
            corrected = cv2.rotate(img, cv2.ROTATE_180)
            return corrected, 180
        elif detected_angle == 270:
            corrected = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            return corrected, 270

        return img, 0

    @classmethod
    def detect_and_unwarp_perspective(cls, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Detect 4-point quadrilateral boundaries in phone camera photos and unwarp to rectangle."""
        h, w = img.shape[:2]
        gray = cls.to_grayscale(img)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        img_area = float(w * h)
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            area = cv2.contourArea(c)
            # Only unwarp if contour occupies a significant part of frame (20% to 98%)
            if area < img_area * 0.20 or area > img_area * 0.98:
                continue

            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                pts = approx.reshape(4, 2).astype(np.float32)

                # Order points: [top-left, top-right, bottom-right, bottom-left]
                rect = np.zeros((4, 2), dtype="float32")
                s = pts.sum(axis=1)
                rect[0] = pts[np.argmin(s)]
                rect[2] = pts[np.argmax(s)]
                diff = np.diff(pts, axis=1)
                rect[1] = pts[np.argmin(diff)]
                rect[3] = pts[np.argmax(diff)]

                tl, tr, br, bl = rect

                # Widths and heights
                width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                max_w = max(int(width_a), int(width_b))

                height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
                max_h = max(int(height_a), int(height_b))

                if max_w > 150 and max_h > 150:
                    dst = np.array(
                        [
                            [0, 0],
                            [max_w - 1, 0],
                            [max_w - 1, max_h - 1],
                            [0, max_h - 1],
                        ],
                        dtype="float32",
                    )
                    m = cv2.getPerspectiveTransform(rect, dst)
                    border_val = (255, 255, 255) if len(img.shape) == 3 else 255
                    unwarped = cv2.warpPerspective(
                        img,
                        m,
                        (max_w, max_h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=border_val,
                    )
                    return unwarped, True

        return img, False

    @classmethod
    def analyze_image_quality(cls, img: np.ndarray) -> ImageQualityProfile:
        """Calculate a lightweight pre-OCR quality profile on the raw image."""
        h, w = img.shape[:2]
        gray = cls.to_grayscale(img)

        # 1. Brightness & Contrast
        brightness = float(np.mean(gray)) / 255.0
        contrast = float(np.std(gray)) / 128.0

        # 2. Sharpness (Laplacian variance normalized)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharpness = float(min(1.0, lap_var / 350.0))

        # 3. Noise Score (median filter residual)
        blurred = cv2.medianBlur(gray, 3)
        noise_diff = float(np.mean(np.abs(gray.astype(np.float32) - blurred.astype(np.float32))))
        noise_score = float(min(1.0, noise_diff / 40.0))

        # 4. Orientation & Skew
        orient = cls.detect_orientation_angle(gray)
        skew = cls.estimate_skew_angle(gray)

        # 5. Low Quality Flag
        is_low_quality = (
            sharpness < 0.20
            or contrast < 0.20
            or noise_score > 0.40
            or min(h, w) < 600
        )

        return ImageQualityProfile(
            orientation=orient,
            rotation_required=(orient != 0),
            skew_angle=round(skew, 2),
            brightness_score=round(brightness, 3),
            contrast_score=round(contrast, 3),
            sharpness_score=round(sharpness, 3),
            noise_score=round(noise_score, 3),
            resolution_width=w,
            resolution_height=h,
            is_low_quality=is_low_quality,
        )

    @classmethod
    def adaptive_binarize(cls, gray: np.ndarray) -> np.ndarray:
        """Apply adaptive Gaussian binarization for tough faded or uneven documents."""
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        return cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8,
        )

    @classmethod
    def trim_borders(cls, gray: np.ndarray) -> np.ndarray:
        """Remove excessive solid black/dark scanner borders."""
        h, w = gray.shape[:2]
        margin_x = int(w * 0.05)
        margin_y = int(h * 0.05)
        if margin_x <= 0 or margin_y <= 0:
            return gray

        _, binary = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_c = max(contours, key=cv2.contourArea)
            bx, by, bw, bh = cv2.boundingRect(largest_c)
            if bw > w * 0.7 and bh > h * 0.7:
                return gray[by : by + bh, bx : bx + bw]
        return gray

    @classmethod
    def preprocess_adaptive(
        cls, raw_img: np.ndarray, quality_profile: Optional[ImageQualityProfile] = None
    ) -> PreprocessingResult:
        """Dynamically apply targeted preprocessing based on image quality signals."""
        profile = quality_profile or cls.analyze_image_quality(raw_img)
        transforms: List[str] = []
        current_img = raw_img

        # 1. Perspective correction for phone photos
        unwarped, applied_unwarp = cls.detect_and_unwarp_perspective(current_img)
        if applied_unwarp:
            current_img = unwarped
            transforms.append("perspective_correction")

        # 2. Resolution control
        res_img, is_upscaled, scale = cls.handle_resolution(current_img)
        if is_upscaled:
            current_img = res_img
            transforms.append(f"rescale_{scale:.2f}x")

        # 3. Grayscale conversion
        gray = cls.to_grayscale(current_img)

        # 4. Orthogonal rotation correction (0, 90, 180, 270)
        orient_angle = profile.orientation
        if orient_angle != 0:
            gray, _ = cls.detect_and_correct_orientation(gray, angle=orient_angle)
            transforms.append(f"rotation_{orient_angle}deg")

        # 5. Deskew for slight tilts (1° to 15°)
        deskewed, skew_angle = cls.deskew_image(gray)
        if abs(skew_angle) >= 0.35:
            gray = deskewed
            transforms.append(f"deskew_{skew_angle:.1f}deg")

        # 6. Lighting and shadow normalization (low brightness or high illumination gradient)
        if profile.brightness_score < 0.45:
            gray = cls.remove_shadows_and_uneven_lighting(gray)
            transforms.append("shadow_removal")

        # 7. Contrast enhancement if low contrast
        if profile.contrast_score < 0.35:
            gray = cls.enhance_contrast_clahe(gray, clip_limit=2.5)
            transforms.append("clahe_contrast")

        # 8. Denoising if noisy scan
        if profile.noise_score > 0.20:
            gray = cls.denoise_image(gray)
            transforms.append("bilateral_denoise")

        if not transforms:
            transforms.append("clean_minimal")

        return PreprocessingResult(
            image=gray,
            skew_angle=skew_angle,
            orientation_angle=orient_angle,
            is_upscaled=is_upscaled,
            scale_factor=scale,
            variant_name="primary_clahe_deskew",
            applied_transforms=transforms,
            quality_profile=profile,
        )

    @classmethod
    def preprocess_primary(cls, raw_img: np.ndarray) -> PreprocessingResult:
        """Standard primary pass: Resolution handling + Grayscale + CLAHE + Denoise + Deskew + Orientation."""
        return cls.preprocess_adaptive(raw_img)

    @classmethod
    def preprocess_alternate(cls, raw_img: np.ndarray) -> PreprocessingResult:
        """Alternate secondary pass: Shadow Removal + Adaptive Binarization + Border Trim."""
        res_img, is_upscaled, scale = cls.handle_resolution(raw_img)
        gray = cls.to_grayscale(res_img)
        deskewed, skew_angle = cls.deskew_image(gray)
        shadow_removed = cls.remove_shadows_and_uneven_lighting(deskewed)
        binarized = cls.adaptive_binarize(shadow_removed)

        transforms = ["rescale" if is_upscaled else "standard", "shadow_removal", "adaptive_binarization"]
        if abs(skew_angle) >= 0.35:
            transforms.append(f"deskew_{skew_angle:.1f}deg")

        return PreprocessingResult(
            image=binarized,
            skew_angle=skew_angle,
            orientation_angle=0,
            is_upscaled=is_upscaled,
            scale_factor=scale,
            variant_name="alternate_shadow_binarized",
            applied_transforms=transforms,
        )
