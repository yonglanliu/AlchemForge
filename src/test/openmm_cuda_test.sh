python - <<'PY'
import openmm as mm
from openmm import unit

system = mm.System()
system.addParticle(39.9)

integrator = mm.VerletIntegrator(1.0 * unit.femtoseconds)
platform = mm.Platform.getPlatformByName("CUDA")

context = mm.Context(
    system,
    integrator,
    platform,
    {
        "DeviceIndex": "0",
        "Precision": "mixed",
    },
)

context.setPositions([
    mm.Vec3(0.0, 0.0, 0.0)
] * unit.nanometers)

print("Platform:", context.getPlatform().getName())
print("Device:", platform.getPropertyValue(context, "DeviceName"))
print("Precision:", platform.getPropertyValue(context, "Precision"))

integrator.step(10)

print("CUDA calculation successful")
PY