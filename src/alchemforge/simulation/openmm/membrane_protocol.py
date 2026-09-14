"""OpenMM protocol for membrane systems: minimization, staged equilibration
(restrained NVT -> restrained NPT with restraints annealed to zero), then
unrestrained NPT production.

Supports Amber (prmtop/inpcrd), GROMACS (gro/top) and CHARMM (psf/crd + toppar)
input systems. Each stage runs in its own Context so ensembles (NVT vs. NPT
membrane barostat) and restraint strength can change between stages; state
(positions/velocities/box vectors) is carried over from one stage to the next.

Example:
    python -m alchemforge.simulation.openmm.membrane_protocol \\
        --format amber --prmtop system.prmtop --inpcrd system.inpcrd \\
        --outdir results/membrane_run
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import openmm as mm
from openmm import app, unit


# ============================================================
# Stage definitions
# ============================================================

@dataclass
class Stage:
    name: str
    ensemble: str                # "NVT" or "NPT"
    n_steps: int
    dt_fs: float = 2.0
    temperature_K: float = 310.0
    pressure_bar: float = 1.0
    restraint_scale: float = 0.0  # fraction of base restraint force constant kept
    report_interval: int = 5000


# Restraint force constant applied to protein backbone + lipid headgroup atoms
# at restraint_scale=1.0. Standard starting point for CHARMM/Amber lipid force
# fields (~1 kcal/mol/A^2 in kJ/mol/nm^2).
BASE_RESTRAINT_KJ_PER_NM2 = 4184.0

# Six-stage anneal: short restrained NVT to relax solvent/lipid packing at a
# small timestep, then four NPT stages that ramp the timestep up and release
# restraints gradually so the membrane area/thickness can equilibrate.
DEFAULT_EQUILIBRATION: list[Stage] = [
    Stage("nvt_1", "NVT", n_steps=125_000, dt_fs=1.0, restraint_scale=1.00),
    Stage("npt_1", "NPT", n_steps=125_000, dt_fs=1.0, restraint_scale=0.50),
    Stage("npt_2", "NPT", n_steps=250_000, dt_fs=2.0, restraint_scale=0.25),
    Stage("npt_3", "NPT", n_steps=250_000, dt_fs=2.0, restraint_scale=0.10),
    Stage("npt_4", "NPT", n_steps=500_000, dt_fs=2.0, restraint_scale=0.00),
]

DEFAULT_PRODUCTION = Stage(
    "production", "NPT", n_steps=25_000_000, dt_fs=2.0, restraint_scale=0.0
)

# Atom names restrained during equilibration: protein backbone + lipid
# phosphate headgroups. Adjust for force fields that name these differently.
DEFAULT_RESTRAINED_ATOM_NAMES = frozenset({"CA", "C", "N", "O", "P"})


# ============================================================
# System loading
# ============================================================

def load_system(system_format: str, **paths):
    """Load topology, positions and a solvated/parameterized OpenMM System.

    `paths` keys depend on `system_format`:
      amber:    prmtop, inpcrd
      gromacs:  gro, top, include_dir (optional)
      charmm:   psf, crd, toppar (list of parameter files), box_vectors (optional, nm)
    """
    system_format = system_format.lower()
    common_kwargs = dict(
        nonbondedMethod=app.PME,
        nonbondedCutoff=1.2 * unit.nanometer,
        constraints=app.HBonds,
        rigidWater=True,
    )

    if system_format == "amber":
        prmtop = app.AmberPrmtopFile(paths["prmtop"])
        inpcrd = app.AmberInpcrdFile(paths["inpcrd"])
        topology = prmtop.topology
        positions = inpcrd.positions
        if inpcrd.boxVectors is not None:
            topology.setPeriodicBoxVectors(inpcrd.boxVectors)
        create_system = lambda: prmtop.createSystem(**common_kwargs)  # noqa: E731

    elif system_format == "gromacs":
        gro = app.GromacsGroFile(paths["gro"])
        top = app.GromacsTopFile(
            paths["top"],
            periodicBoxVectors=gro.getPeriodicBoxVectors(),
            includeDir=paths.get("include_dir"),
        )
        topology = top.topology
        positions = gro.positions
        create_system = lambda: top.createSystem(**common_kwargs)  # noqa: E731

    elif system_format == "charmm":
        psf = app.CharmmPsfFile(paths["psf"])
        crd_path = str(paths["crd"])
        crd = app.PDBFile(crd_path) if crd_path.endswith(".pdb") else app.CharmmCrdFile(crd_path)
        params = app.CharmmParameterSet(*paths["toppar"])
        if "box_vectors" in paths:
            psf.setBox(*paths["box_vectors"])
        topology = psf.topology
        positions = crd.positions
        create_system = lambda: psf.createSystem(params, **common_kwargs)  # noqa: E731

    else:
        raise ValueError(f"Unsupported system format: {system_format}")

    return topology, positions, create_system


# ============================================================
# Restraints
# ============================================================

def add_position_restraints(system, topology, positions, atom_names, force_constant):
    """Harmonically restrain the named atoms to their current coordinates."""
    force = mm.CustomExternalForce("k_restr * ((x-x0)^2 + (y-y0)^2 + (z-z0)^2)")
    force.addGlobalParameter("k_restr", force_constant)
    force.addPerParticleParameter("x0")
    force.addPerParticleParameter("y0")
    force.addPerParticleParameter("z0")

    for atom in topology.atoms():
        if atom.name in atom_names:
            pos = positions[atom.index].value_in_unit(unit.nanometer)
            force.addParticle(atom.index, pos)

    system.addForce(force)
    return force


# ============================================================
# Platform selection
# ============================================================

def select_platform(preferred="CUDA"):
    for name in (preferred, "CUDA", "OpenCL", "CPU"):
        try:
            return mm.Platform.getPlatformByName(name)
        except Exception:
            continue
    raise RuntimeError("No OpenMM platform is available")


# ============================================================
# Protocol driver
# ============================================================

def run_protocol(
    topology,
    positions,
    create_system,
    stages,
    output_dir,
    restrained_atom_names=DEFAULT_RESTRAINED_ATOM_NAMES,
    base_restraint_kj_per_nm2=BASE_RESTRAINT_KJ_PER_NM2,
    platform_name="CUDA",
    restart_state=None,
):
    """Run `stages` in sequence, each in its own Context, carrying over
    positions/velocities/box vectors from the previous stage.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    platform = select_platform(platform_name)

    state = None
    if restart_state is not None:
        with open(restart_state) as fh:
            state = mm.XmlSerializer.deserialize(fh.read())

    for stage in stages:
        system = create_system()

        if stage.restraint_scale > 0:
            add_position_restraints(
                system,
                topology,
                positions,
                restrained_atom_names,
                base_restraint_kj_per_nm2 * stage.restraint_scale,
            )

        if stage.ensemble == "NPT":
            system.addForce(
                mm.MonteCarloMembraneBarostat(
                    stage.pressure_bar * unit.bar,
                    0 * unit.bar * unit.nanometer,
                    stage.temperature_K * unit.kelvin,
                    mm.MonteCarloMembraneBarostat.XYIsotropic,
                    mm.MonteCarloMembraneBarostat.ZFree,
                )
            )

        integrator = mm.LangevinMiddleIntegrator(
            stage.temperature_K * unit.kelvin,
            1.0 / unit.picosecond,
            stage.dt_fs * unit.femtosecond,
        )

        simulation = app.Simulation(topology, system, integrator, platform)

        if state is None:
            simulation.context.setPositions(positions)
            simulation.minimizeEnergy()
            simulation.context.setVelocitiesToTemperature(stage.temperature_K * unit.kelvin)
        else:
            simulation.context.setPeriodicBoxVectors(*state.getPeriodicBoxVectors())
            simulation.context.setPositions(state.getPositions())
            simulation.context.setVelocities(state.getVelocities())

        simulation.reporters.append(
            app.StateDataReporter(
                str(output_dir / f"{stage.name}.log"),
                stage.report_interval,
                step=True,
                time=True,
                temperature=True,
                potentialEnergy=True,
                volume=True,
                speed=True,
            )
        )
        simulation.reporters.append(
            app.DCDReporter(str(output_dir / f"{stage.name}.dcd"), stage.report_interval)
        )

        simulation.step(stage.n_steps)

        state = simulation.context.getState(getPositions=True, getVelocities=True)
        with open(output_dir / f"{stage.name}.xml", "w") as fh:
            fh.write(mm.XmlSerializer.serialize(state))

    return state


# ============================================================
# CLI
# ============================================================

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", required=True, choices=["amber", "gromacs", "charmm"])
    parser.add_argument("--prmtop")
    parser.add_argument("--inpcrd")
    parser.add_argument("--gro")
    parser.add_argument("--top")
    parser.add_argument("--include-dir")
    parser.add_argument("--psf")
    parser.add_argument("--crd")
    parser.add_argument("--toppar", nargs="+")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--platform", default="CUDA")
    parser.add_argument("--restart-state", help="State XML to resume from, skipping equilibration")
    parser.add_argument("--production-only", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    format_paths = {
        "amber": dict(prmtop=args.prmtop, inpcrd=args.inpcrd),
        "gromacs": dict(gro=args.gro, top=args.top, include_dir=args.include_dir),
        "charmm": dict(psf=args.psf, crd=args.crd, toppar=args.toppar),
    }
    topology, positions, create_system = load_system(args.format, **format_paths[args.format])

    stages = [] if args.production_only else list(DEFAULT_EQUILIBRATION)
    stages.append(DEFAULT_PRODUCTION)

    run_protocol(
        topology,
        positions,
        create_system,
        stages,
        args.outdir,
        platform_name=args.platform,
        restart_state=args.restart_state,
    )


if __name__ == "__main__":
    main()
