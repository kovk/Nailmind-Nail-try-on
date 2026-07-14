from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    inference_host: str = "0.0.0.0"
    inference_port: int = 8090
    inference_token: str = ""
    inference_mock: bool = True
    editor_backend: str = "mock"
    model_dir: str = "/models/nailmind-editor"
    model_id: str = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    flux2_model_dir: str = ""
    flux2_model_id: str = "black-forest-labs/FLUX.2-klein-4B"
    flux2_steps: int = 4
    flux2_guidance_scale: float = 1.0
    flux2_inpaint_strength: float = 0.20
    flux2_inpaint_padding: int = 16
    flux2_inpaint_edge_width: int = 8
    flux2_seed: int = 42
    flux2_min_image_side: int = 768
    flux2_max_image_side: int = 2048
    nailseg_model_path: str = "inference/models/nailseg-yolo11s-best.pt"
    user_nail_segmenter: str = "yolo"
    user_nail_allow_yolo_fallback: bool = False
    style_asset_segmenter: str = "sam3_text"
    sam3_checkpoint_path: str = "/root/autodl-tmp/models/sam3/sam3.pt"
    sam3_prompt: str = "fingernail"
    sam3_min_score: float = 0.35
    sam3_allow_yolo_fallback: bool = False
    style_asset_dir: str = "inference/outputs/style-assets"
    public_base_url: str = ""
    device: str = "cuda"
    torch_dtype: str = "float16"
    max_image_side: int = 2048
    model_max_image_side: int = 2048
    style_asset_canonical_width: int = 256
    style_asset_canonical_height: int = 384
    style_asset_mask_erode: int = 3
    inference_steps: int = 8
    guidance_scale: float = 1.4
    strength: float = 0.72
    local_edit_steps: int = 6
    local_edit_guidance_scale: float = 1.15
    local_edit_strength: float = 0.28
    local_edit_crop_padding: int = 72
    reference_adapter_dir: str = ""
    reference_adapter_subfolder: str = ""
    reference_adapter_weight_name: str = ""
    reference_adapter_scale: float = 0.55
    reference_image_size: int = 512
    preserve_original_resolution: bool = True
    production_mode: bool = False
    require_style_nail_asset: bool = False
    min_valid_nails: int = 4
    registration_mode: str = "tps"
    enable_edge_repair: bool = True
    edge_repair_strength: float = 0.12
    overlay_alpha: float = 0.94
    overlay_highlight_alpha: float = 0.28
    enable_cpu_offload: bool = False
    preload_model_on_startup: bool = False
    allow_heuristic_mask: bool = True
    mask_dilate: int = 12
    mask_blur: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
