"""Configurable reference reconstruction parameters (scene units are metres)."""
from dataclasses import dataclass

@dataclass
class CharacterConfig:
    head_scale: float = 1.0
    head_tilt_degrees: float = 11.0
    eye_radius: float = .335
    eye_spacing: float = .445
    muzzle_width: float = .405
    ear_angle: float = 0.0
    body_width: float = .84
    fur_density: float = 32000.0  # strands per square scene unit
    fur_length: float = .045
    tail_curl: float = 1.12
    scarf_width: float = .39
    cream_color: tuple = (.59, .43, .275)
    mask_color: tuple = (.034, .023, .018)
    seed: int = 314159
    preview_samples: int = 48
    final_samples: int = 256
    final_resolution: int = 2048
