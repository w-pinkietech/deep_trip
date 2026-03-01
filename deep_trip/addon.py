from ten_runtime import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import DeepTripExtension

@register_addon_as_extension("deep_trip")
class DeepTripExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        ten_env.log_info("on_create_instance")
        ten_env.on_create_instance_done(DeepTripExtension(name), context)
