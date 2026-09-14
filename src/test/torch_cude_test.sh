python - <<'PY'
import torch

print("PyTorch:", torch.__version__)
print("CUDA build:", torch.version.cuda)
print("Supported archs:", torch.cuda.get_arch_list())

print("CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("Capability:", torch.cuda.get_device_capability(0))

    x = torch.randn(1000, 1000, device="cuda")
    y = x @ x
    print("GPU calculation works:", y.device)
PY