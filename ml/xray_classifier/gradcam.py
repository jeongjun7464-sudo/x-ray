import numpy as np
import torch
from PIL import Image


class GradCAM:
    """Framework-native Grad-CAM for a selected convolution layer."""

    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model
        self.activations = None
        self.gradients = None
        self._forward = target_layer.register_forward_hook(self._save_activation)
        self._backward = target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, _module, _inputs, output):
        self.activations = output.detach()

    def _save_gradient(self, _module, _grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def __call__(self, image: torch.Tensor, class_index: int | None = None) -> np.ndarray:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(image)
        index = int(logits.argmax(1)[0]) if class_index is None else class_index
        logits[0, index].backward()
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        heatmap = torch.relu((weights * self.activations).sum(1))[0]
        heatmap -= heatmap.min()
        heatmap /= heatmap.max().clamp_min(1e-8)
        return heatmap.cpu().numpy()

    def close(self):
        self._forward.remove()
        self._backward.remove()


def overlay_heatmap(image: Image.Image, heatmap: np.ndarray, alpha: float = 0.4) -> Image.Image:
    base = image.convert("RGB")
    heat = Image.fromarray((heatmap * 255).astype("uint8")).resize(base.size)
    zeros = Image.new("L", base.size)
    color = Image.merge("RGB", (heat, zeros, Image.eval(heat, lambda x: 255 - x)))
    return Image.blend(base, color, alpha)
