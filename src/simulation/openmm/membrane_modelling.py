from __future__ import division, absolute_import

__author__ = "Yonglan Liu"

import gc
import os
from math import ceil, floor
from typing import Iterable

import numpy as np
from simulation.openmm import Vec3, app
from openmm.app import Modeller, PDBFile, ForceField, Topology
from openmm.unit import nanometer, molar, is_quantity, norm
from copy import deepcopy
from openmm.app.internal import compiled
from collections import defaultdict, namedtuple
from simulation.openmm import System, Context, NonbondedForce, AmoebaVdwForce, AmoebaMultipoleForce, CustomNonbondedForce, HarmonicBondForce, HarmonicAngleForce, VerletIntegrator, LangevinIntegrator, LocalEnergyMinimizer
from openmm.app.modeller import elem, _CellList
from openmm.app.forcefield import AllBonds, CutoffNonPeriodic, CutoffPeriodic, DrudeGenerator, _getDataDirectories
import sys
import openmm.unit as unit

class MembraneModeller(Modeller):
    def __init__(self, topology, positions):
        super().__init__(topology, positions)

    @staticmethod
    def _residue_key(residue):
        chain_id = residue.chain.id if residue.chain is not None else ""
        return (chain_id, residue.id, residue.insertionCode, residue.name)

    @staticmethod
    def _to_nm_array(positions):
        if is_quantity(positions):
            return np.array(positions.value_in_unit(nanometer), dtype=float)
        else:
            # plain list of Vec3
            return np.array([[v.x, v.y, v.z] for v in positions], dtype=float)

    @staticmethod
    def _strip_names(ref_names):
        if ref_names is None:
            return []
        if isinstance(ref_names, str):
            return [n.strip() for n in ref_names.split(",") if n.strip()]
        return [n.strip() for n in ref_names if n.strip()]

    @staticmethod
    def _value_in_nm(quantity):
        return quantity.value_in_unit(nanometer) if is_quantity(quantity) else quantity

    def addSolventWithExistingMembrane(
        self,
        forcefield: ForceField,
        solvent_model = "tip3p",
        pbc_x_vector = None, # Vec3(Lx, 0, 0) * nanometer
        pbc_y_vector = None, # Vec3(0, Ly, 0) * nanometer
        padding=1.0 * nanometer,
        boxsize=None, # Vec3(Lx, Ly, Lz) * nanometer
        box_vectors=None, # (Vec3(Lx, 0, 0) * nanometer, Vec3(0, Ly, 0) * nanometer, Vec3(0, 0, Lz) * nanometer)
        positiveIon="Na+",
        negativeIon="Cl-",
        ionicStrength=0 * molar,
        neutralize=True,
        write_structure=False,
        residueTemplates=dict(),
    ):
        """
        Add solvent to a system with an existing lipid membrane (and optional pre-existing water).

        This method adds water molecules and, if requested, neutralizing counterions and additional salt to the system.

        ---Periodic boundary conditions (PBC)---:

        If the input system already defines PBC, those box vectors are reused. Water will be added to fill that existing box.
        If you do not want to use the original PBC, you should remove them before calling this method.
        If the system does not define PBC, the box will be constructed as follows:
            1. If pbc_x_vector and pbc_y_vector are provided, they are used together with the specified padding (for the z dimension).
            2. Otherwise, the x and y dimensions are inferred from the membrane, and the z dimension is determined from the padding.
        The membrane extent is estimated from the positions of lipid head-group atoms (e.g., “P” atoms), which provides a more robust measure than using all lipid atoms.

        Once the periodic box is defined, the system is solvated within that box.

        ---Water handling---:

        Existing water molecules in the input system are preserved; the method only fills previously empty space with additional water.
        Water molecules that fall inside the membrane (e.g., in the hydrophobic core) are removed after solvation.

        ---Ion placement---:

        Counterions are added to neutralize the system if requested.
        Additional ions are added to achieve the specified ionic strength by replacing randomly selected water molecules.
        """
        # All accept lipid names
        lipid_names = ["POPC","POPE","DMPC","DOPC","DPPC","DLPC","DLPE","POP"]
        # Save original waters so they are never deleted.
        original_water_keys = {
            self._residue_key(res)
            for res in self.topology.residues()
            if res.name in ["HOH","WAT"]
        }
        print(f'The original system contains {len(original_water_keys)} water molecules')

        # -------------------------------------------------
        # Positions as plain numpy arrays in nm.
        # -------------------------------------------------
        all_pos = self._to_nm_array(self.positions)
        sys_min = np.min(all_pos, axis=0)
        sys_max = np.max(all_pos, axis=0)
        sys_zmin = sys_min[2]
        sys_zmax = sys_max[2]

        # -------------------------------------------------
        # Lipid atom positions from the existing structure.
        # -------------------------------------------------
        lipid_atom_indices = [
            atom.index
            for atom in self.topology.atoms()
            if atom.residue.name in lipid_names
            and atom.name == "P"
        ]

        lipid_pos = all_pos[lipid_atom_indices, :]
        lipid_zmin = float(np.min(lipid_pos[:, 2]))
        lipid_zmax = float(np.max(lipid_pos[:, 2]))

        # -----------------------------------------------------
        #                   Determine PBC
        #
        # Priority: box_vectors > boxsize > (pbc_x_vector/pbc_y_vector
        # for XY, padding for Z) > fully inferred from system extents + padding.
        # Higher-priority inputs are only used once; lower-priority ones
        # never silently override an axis that was already resolved.
        # -----------------------------------------------------
        box_x = box_y = box_z = None

        if box_vectors is not None:
            vector_x, vector_y, vector_z = (self._value_in_nm(v) for v in box_vectors)
            box_x, box_y, box_z = vector_x[0], vector_y[1], vector_z[2]
            print(f'Using explicit box_vectors: {box_vectors}')

        elif boxsize is not None:
            box_x, box_y, box_z = self._value_in_nm(boxsize)
            print(f'Using explicit boxsize: {boxsize}')

        else:
            padding_nm = self._value_in_nm(padding) if padding is not None else 0.0
            box_z = float(sys_zmax - sys_zmin + 2.0 * padding_nm)

            if (pbc_x_vector is not None) and (pbc_y_vector is not None):
                box_x = self._value_in_nm(pbc_x_vector)[0]
                box_y = self._value_in_nm(pbc_y_vector)[1]
            else:
                box_x = float(sys_max[0] - sys_min[0] + 2.0 * padding_nm)
                box_y = float(sys_max[1] - sys_min[1] + 2.0 * padding_nm)

            print(f'Derived box from padding: ({box_x}, {box_y}, {box_z}) nm')

        if (box_x is None) or (box_y is None) or (box_z is None):
            raise ValueError("PBC cannot be determined; set padding, boxsize, or box_vectors")

        box_vector = (Vec3(box_x, 0, 0),
                      Vec3(0, box_y, 0),
                      Vec3(0, 0, box_z)) * nanometer
        print(f'New PBC: {box_vector}')

        # -----------------------------------------------------
        #                    Copy system
        #
        # Copy into a new Topology (rather than mutating self.topology in
        # place) so self is left untouched if addSolvent below fails.
        # -----------------------------------------------------
        newTopology = Topology()
        newTopology.setUnitCellDimensions(Vec3(box_x, box_y, box_z) * nanometer)
        newTopology.setPeriodicBoxVectors(box_vector)

        newAtoms = {}
        newResidueTemplates = dict()
        for chain in self.topology.chains():
            newChain = newTopology.addChain(chain.id)
            for residue in chain.residues():
                newResidue = newTopology.addResidue(residue.name, newChain, residue.id, residue.insertionCode)
                if residue in residueTemplates:
                    newResidueTemplates[newResidue] = residueTemplates[residue]
                for atom in residue.atoms():
                    newAtom = newTopology.addAtom(atom.name, atom.element, newResidue, atom.id, atom.formalCharge)
                    newAtoms[atom] = newAtom
        for bond in self.topology.bonds():
            newTopology.addBond(newAtoms[bond[0]], newAtoms[bond[1]], bond.type, bond.order)

        # Atom order mirrors self.topology.atoms(), so positions carry over as-is (with units).
        newPositions = deepcopy(self.positions) if len(self.positions) > 0 else []

        # -----------------------------------------------------
        #       Add solvent around the whole system
        # -----------------------------------------------------

        modeller = Modeller(newTopology, newPositions)
        print(f'PBC: {newTopology.getPeriodicBoxVectors()}')
        modeller.topology.setPeriodicBoxVectors(newTopology.getPeriodicBoxVectors())
        modeller.topology.setUnitCellDimensions(newTopology.getUnitCellDimensions())

        modeller.addSolvent(
            forcefield,
            model=solvent_model,
            neutralize=False,
            residueTemplates=newResidueTemplates,
        )

        # Recompute positions after solvation.
        solv_pos = self._to_nm_array(modeller.positions)

        to_delete = []
        addedChain = list(modeller.topology.chains())[-1]
        for residue in addedChain.residues():
            if residue.name not in ["HOH", "WAT"]:
                continue

            key = self._residue_key(residue)

            if len(original_water_keys) > 0:
                if key in original_water_keys:
                    continue  # never delete original waters

            oxy_index = None
            for atom in residue.atoms():
                if atom.element is not None and atom.element.symbol == "O":
                    oxy_index = atom.index
                    break
            if oxy_index is None:
                continue

            oxy_pos = solv_pos[oxy_index]
            z = oxy_pos[2]

            # Delete waters in the membrane core
            if lipid_zmin < z < lipid_zmax:
                to_delete.append(residue)

        if len(to_delete) > 0:
            modeller.delete(to_delete)


        # Update this object in-place.
        newResidueTemplates = {}
        for r1, r2 in zip(self.topology.residues(), modeller.topology.residues()):
            if r1 in residueTemplates:
                newResidueTemplates[r2] = residueTemplates[r1]

        self.topology = modeller.topology
        self.positions = modeller.positions

        # Select a subset of water molecules to replace with ions, ignoring
        # those within a certain distance from either leaflet of the membrane.
        waterPos = {}  # redo because modeller.delete changes chain indexes
        for chain in list(modeller.topology.chains()):
            for residue in chain.residues():
                if residue.name in ['HOH', 'WAT']:
                    for atom in residue.atoms():
                        if atom.element.symbol == "O":
                            waterPos[residue] = modeller.positions[atom.index]

        # Total number of water molecules
        # Use this number to avoid underestimating the concentration of ions
        # in _addIons after we exclude waters close to lipids.
        numTotalWaters = len(waterPos)

        # Ignore waters that are within a certain distance of the membrane
        lipidOffset = 0.25
        upperZBoundary = (lipid_zmax + lipidOffset)
        lowerZBoundary = (lipid_zmin - lipidOffset)
        waterResidues = list(waterPos)
        for wRes in waterResidues:
            waterZ = waterPos[wRes][2]
            if lowerZBoundary < waterZ.value_in_unit(nanometer) < upperZBoundary:
                del waterPos[wRes]

        gc.collect()
        if write_structure:
            with open("addSolventWithExistingMembrane_sol.pdb", "w") as f:
                PDBFile.writeFile(self.topology, self.positions, f)

        self._addIons(forcefield, numTotalWaters, waterPos, positiveIon=positiveIon, negativeIon=negativeIon, ionicStrength=ionicStrength, neutralize=neutralize, residueTemplates=newResidueTemplates)
        if write_structure:
            with open("addSolventWithExistingMembrane_sol_ion.pdb", "w") as f:
                PDBFile.writeFile(self.topology, self.positions, f)
        

    def addMembrane(
        self,
        forcefield,
        lipidType='POPC',
        scale_factor=0.6,
        membraneCenterZ=0 * nanometer,
        x_padding=1.0 * nanometer,
        y_padding=1.0 * nanometer,
        z_padding=1.0 * nanometer,
        positiveIon='Na+',
        negativeIon='Cl-',
        ionicStrength=0 * molar,
        neutralize=True,
        write_structure=False,
        residueTemplates=dict(),
        platform=None
    ):

        # ============================================================
        # Determine membrane boundaries and trim excess water/lipids
        # ============================================================
        
        # ------------------------------------------------------------
        # 1. Read lipid patch
        # ------------------------------------------------------------
        lipid_types = (
            'POPC', 'POPE', 'DLPC', 'DLPE',
            'DMPC', 'DOPC', 'DPPC'
        )

        lipid_types_3resn = {
            "POPC": "POP",
            'POPE': "POP",
            'DLPC': 'DLP',
            'DLPE': 'DLP',
            'DMPC': 'DMP',
            'DOPC': 'DOP',
            'DPPC': 'DPP',
        }
        if 'topology' in dir(lipidType) and 'positions' in dir(lipidType):
            patch = lipidType
        elif lipidType.upper() in lipid_types:
            openmm_path = os.path.dirname(app.__file__)
            patch = PDBFile(os.path.join(openmm_path,'data', lipidType.upper() + '.pdb'))
        else:
            raise ValueError('Unsupported lipid type: ' + lipidType)

        # ------------------------------------------------------------
        # 2. Convert all input lengths to plain nm floats
        # ------------------------------------------------------------
        if is_quantity(membraneCenterZ):
            membraneCenterZ = membraneCenterZ.value_in_unit(nanometer)

        if is_quantity(x_padding):
            x_padding = x_padding.value_in_unit(nanometer)

        if is_quantity(y_padding):
            y_padding = y_padding.value_in_unit(nanometer)

        if is_quantity(z_padding):
            z_padding = z_padding.value_in_unit(nanometer)

        # ------------------------------------------------------------
        # 3. Protein coordinates and dimensions
        # ------------------------------------------------------------
        proteinPos = self.positions.value_in_unit(nanometer)
        proteinMinPos = Vec3(*[min(p[i] for p in proteinPos) for i in range(3)])
        proteinMaxPos = Vec3(*[max(p[i] for p in proteinPos) for i in range(3)])
        proteinSize = proteinMaxPos - proteinMinPos
        proteinCenterPos = (proteinMinPos + proteinMaxPos) / 2.0

        # Keep XY center from protein, set Z to membraneCenterZ
        proteinCenterPos = Vec3(proteinCenterPos[0], proteinCenterPos[1], membraneCenterZ)

        # ------------------------------------------------------------
        # 4. Membrane patch dimensions
        # ------------------------------------------------------------
        patchPos = patch.positions.value_in_unit(nanometer)
        patchSize = patch.topology.getUnitCellDimensions().value_in_unit(nanometer)
        patchMinPos = Vec3(*[min(p[i] for p in patchPos) for i in range(3)])
        patchMaxPos = Vec3(*[max(p[i] for p in patchPos) for i in range(3)])
        patchCenterPos = (patchMinPos + patchMaxPos) / 2.0

        # ------------------------------------------------------------
        # 5. Desired final XY dimensions
        #
        # IMPORTANT:
        # final dimensions = protein dimensions + 2 * padding
        # ------------------------------------------------------------
        paddingSizeX = proteinSize[0] + 2.0 * x_padding
        paddingSizeY = proteinSize[1] + 2.0 * y_padding

        print(f"Protein XY: "f"({proteinSize[0]}, {proteinSize[1]}) nm")

        print(f"Desired final XY: ({paddingSizeX}, {paddingSizeY}) nm")

        # ------------------------------------------------------------
        # 6. Number of lipid patches needed
        # ------------------------------------------------------------
        nx = int(ceil(paddingSizeX / patchSize[0]))
        ny = int(ceil(paddingSizeY / patchSize[1]))

        boxSizeX = nx * patchSize[0]
        boxSizeY = ny * patchSize[1]

        print(f"Temporary membrane XY: ({boxSizeX}, {boxSizeY}) nm")

        # ------------------------------------------------------------
        # 7. Record lipid residue bonds
        # ------------------------------------------------------------
        resBonds = defaultdict(list)

        for bond in patch.topology.bonds():
            resBonds[bond[0].residue].append(bond)

        # ------------------------------------------------------------
        # 8. Identify membrane leaflets
        # ------------------------------------------------------------
        numLipidAtoms = 0
        resMeanZ = {}
        membraneMeanZ = 0.0

        for res in patch.topology.residues():
            if res.name not in ['HOH', 'WAT']:

                numResAtoms = 0
                sumZ = 0.0

                for atom in res.atoms():
                    numResAtoms += 1
                    sumZ += patchPos[atom.index][2]

                numLipidAtoms += numResAtoms
                membraneMeanZ += sumZ
                resMeanZ[res] = sumZ / numResAtoms

        membraneMeanZ /= numLipidAtoms

        lipidLeaf = {res: 0 if resMeanZ[res] < membraneMeanZ else 1 for res in resMeanZ}

        # ------------------------------------------------------------
        # 9. Scaled protein coordinates
        # ------------------------------------------------------------
        scaledProteinPos = [None] * len(proteinPos)

        for i, p in enumerate(proteinPos):

            p = p - proteinCenterPos

            p = Vec3(scale_factor * p[0], scale_factor * p[1], p[2])

            scaledProteinPos[i] = p + proteinCenterPos

        # ------------------------------------------------------------
        # 10. Create temporary membrane topology
        # ------------------------------------------------------------
        membraneTopology = Topology()
        membranePos = []

        boxSizeZ = patchSize[2]

        if self.topology.getUnitCellDimensions() is not None:
            boxSizeZ = max(boxSizeZ, self.topology.getUnitCellDimensions()[2].value_in_unit(nanometer) + 2.0 * z_padding)
        else:
            boxSizeZ = max(boxSizeZ, proteinSize[2] + 2.0 * z_padding)

        membraneTopology.setUnitCellDimensions((boxSizeX, boxSizeY, boxSizeZ))

        # ------------------------------------------------------------
        # 11. Spatial cell lists
        # ------------------------------------------------------------
        overlapCutoff = 0.22

        addedWater = []
        addedLipids = []
        removedFromLeaf = [0, 0]

        vectors = (membraneTopology.getPeriodicBoxVectors().value_in_unit(nanometer))

        proteinCells = _CellList(proteinPos, overlapCutoff, vectors, False)

        scaledProteinCells = _CellList(scaledProteinPos, overlapCutoff, vectors, False)

        # ------------------------------------------------------------
        # 12. Build temporary membrane
        # ------------------------------------------------------------
        for x in range(nx):
            for y in range(ny):

                offset = (proteinCenterPos - patchCenterPos + Vec3((x - 0.5 * (nx - 1)) * patchSize[0], (y - 0.5 * (ny - 1)) * patchSize[1],0))

                for res in patch.topology.residues():

                    resPos = [patchPos[atom.index] + offset for atom in res.atoms()]

                    if res.name not in ['HOH', 'WAT']:

                        referencePosLists = [proteinPos, scaledProteinPos]
                        cellLists = [proteinCells, scaledProteinCells]

                    else:

                        referencePosLists = [scaledProteinPos]
                        cellLists = [scaledProteinCells]

                    overlap = False
                    nearest = nx * patchSize[0]

                    for cells, referencePos in zip(cellLists,referencePosLists):

                        if overlap:
                            break

                        for index, atom in enumerate(res.atoms()):

                            pos = resPos[index]

                            for atom_index in cells.neighbors(pos):

                                distance = norm(pos - referencePos[atom_index])

                                if distance < overlapCutoff:
                                    overlap = True
                                    break

                                nearest = min(nearest, distance)

                            if overlap:
                                break

                    if res.name in ['HOH', 'WAT']:

                        if not overlap:
                            addedWater.append((res, resPos))

                    else:

                        if overlap:
                            removedFromLeaf[lipidLeaf[res]] += 1

                        else:
                            addedLipids.append((nearest, res, resPos))

        skipFromLeaf = [max(removedFromLeaf) - removedFromLeaf[i] for i in (0, 1)]

        # ------------------------------------------------------------
        # 13. Add lipids
        # ------------------------------------------------------------
        newAtoms = {}

        lipidChain = membraneTopology.addChain()
        lipidResNum = 1

        for nearest, residue, pos in addedLipids:
            leaf = lipidLeaf[residue]
            if skipFromLeaf[leaf] > 0:
                skipFromLeaf[leaf] -= 1
            else:
                newResidue = membraneTopology.addResidue(residue.name, lipidChain, str(lipidResNum), residue.insertionCode)
                lipidResNum += 1

                for atom in residue.atoms():

                    newAtom = membraneTopology.addAtom(atom.name, atom.element, newResidue, atom.id, atom.formalCharge)
                    newAtoms[atom] = newAtom

                membranePos += pos

                for bond in resBonds[residue]:

                    membraneTopology.addBond(
                        newAtoms[bond[0]],
                        newAtoms[bond[1]],
                        bond.type,
                        bond.order
                    )

        del lipidLeaf
        del addedLipids

        # ------------------------------------------------------------
        # 14. Add membrane water
        # ------------------------------------------------------------
        solventChain = membraneTopology.addChain()

        for residue, pos in addedWater:

            newResidue = membraneTopology.addResidue(
                residue.name,
                solventChain,
                residue.id,
                residue.insertionCode
            )

            for atom in residue.atoms():

                newAtom = membraneTopology.addAtom(
                    atom.name,
                    atom.element,
                    newResidue,
                    atom.id,
                    atom.formalCharge
                )

                newAtoms[atom] = newAtom

            membranePos += pos

            for bond in resBonds[residue]:

                membraneTopology.addBond(
                    newAtoms[bond[0]],
                    newAtoms[bond[1]],
                    bond.type,
                    bond.order
                )

        del newAtoms
        del addedWater
        del resBonds

        gc.collect()

        # ------------------------------------------------------------
        # 15. Create membrane system + fixed protein
        # ------------------------------------------------------------
        system = forcefield.createSystem(
            membraneTopology,
            nonbondedMethod=CutoffPeriodic,
            residueTemplates=residueTemplates
        )

        proteinSystem = forcefield.createSystem(
            self.topology,
            nonbondedMethod=CutoffNonPeriodic,
            residueTemplates=residueTemplates
        )

        numMembraneParticles = system.getNumParticles()
        numProteinParticles = proteinSystem.getNumParticles()

        for i in range(numProteinParticles):
            system.addParticle(0.0)

        nonbonded = None

        for f1, f2 in zip(
            system.getForces(),
            proteinSystem.getForces()
        ):

            if isinstance(f1, NonbondedForce):

                nonbonded = f2

                for i in range(numProteinParticles):

                    f1.addParticle(
                        *f2.getParticleParameters(i)
                    )

                    for j in scaledProteinCells.neighbors(
                        scaledProteinPos[i]
                    ):

                        if j < i:

                            f1.addException(
                                i + numMembraneParticles,
                                j + numMembraneParticles,
                                0.0,
                                1.0,
                                0.0
                            )

            elif isinstance(f1, CustomNonbondedForce):

                for i in range(numProteinParticles):

                    f1.addParticle(
                        f2.getParticleParameters(i)
                    )

                    for j in scaledProteinCells.neighbors(
                        scaledProteinPos[i]
                    ):

                        if j < i:

                            f1.addExclusion(
                                i + numMembraneParticles,
                                j + numMembraneParticles
                            )

        if nonbonded is None:
            raise ValueError(
                'The ForceField does not specify a NonbondedForce'
            )

        mergedPositions = membranePos + scaledProteinPos

        del membranePos

        del scaledProteinCells

        gc.collect()

        # ------------------------------------------------------------
        # 16. Relax membrane
        # ------------------------------------------------------------
        steps = int(
            max(proteinSize.x, proteinSize.y) * 10
        ) + 1

        integrator = LangevinIntegrator(
            10.0,
            50.0,
            0.001
        )

        if platform is None:
            context = Context(
                system,
                integrator
            )
        else:
            context = Context(
                system,
                integrator,
                platform
            )

        context.setPositions(mergedPositions)

        LocalEnergyMinimizer.minimize(
            context,
            10.0,
            30
        )

        try:
            import numpy as np

            hasNumpy = True

            proteinPosArray = np.array(
                proteinPos
            )

            scaledProteinPosArray = np.array(
                scaledProteinPos
            )

        except:
            hasNumpy = False

        for i in range(steps):

            weight1 = i / (steps - 1)
            weight2 = 1.0 - weight1

            mergedPositions = (
                context
                .getState(positions=True)
                .getPositions(
                    asNumpy=hasNumpy
                )
                .value_in_unit(nanometer)
            )

            if hasNumpy:

                mergedPositions[
                    numMembraneParticles:
                ] = (
                    weight1 * proteinPosArray
                    + weight2 * scaledProteinPosArray
                )

            else:

                for j in range(len(proteinPos)):

                    mergedPositions[
                        j + numMembraneParticles
                    ] = (
                        weight1 * proteinPos[j]
                        + weight2 * scaledProteinPos[j]
                    )

            context.setPositions(
                mergedPositions
            )

            integrator.step(20)

        # ------------------------------------------------------------
        # 17. Add membrane to protein
        # ------------------------------------------------------------
        modeller = Modeller(self.topology, self.positions)

        modeller.add(membraneTopology, context.getState(positions=True).getPositions()[:numMembraneParticles])

        # Use temporary membrane box first
        modeller.topology.setPeriodicBoxVectors(membraneTopology.getPeriodicBoxVectors())

        del context
        del system
        del integrator

        if write_structure:
            with open("addMembrane_before_sol.pdb", "w") as f:
                PDBFile.writeFile(modeller.topology, modeller.positions, f)

        # ------------------------------------------------------------
        # 18. Add extra water if Z box needs expansion
        # ------------------------------------------------------------
        needExtraWater = (boxSizeZ > patchSize[2])

        if needExtraWater:
            newResidueTemplates = {}

            for r1, r2 in zip(self.topology.residues(), modeller.topology.residues()):

                if r1 in residueTemplates:
                    newResidueTemplates[r2] = (residueTemplates[r1])

            modeller.addSolvent(forcefield, neutralize=False, residueTemplates=newResidueTemplates)

        # ------------------------------------------------------------
        # 19. Find all water residues
        # ------------------------------------------------------------
        waterPos = {}

        for residue in modeller.topology.residues():
            if residue.name in ['HOH', 'WAT']:
                for atom in residue.atoms():
                    if atom.element == elem.oxygen:
                        waterPos[residue] = (modeller.positions[atom.index].value_in_unit(nanometer))
                        break

        # ------------------------------------------------------------
        # 20. Calculate membrane Z boundaries
        # ------------------------------------------------------------
        lipidNames = {res.name for res in patch.topology.residues() if res.name not in {"HOH", "WAT"}}
        print("Lipid residue names:", lipidNames)

        lipidZMax = -float("inf")
        lipidZMin = float("inf")

        for res in modeller.topology.residues():
            if res.name in lipidNames:
                for atom in res.atoms():
                    atomZ = (modeller.positions[atom.index][2].value_in_unit(nanometer))

                    lipidZMax = max(lipidZMax, atomZ)
                    lipidZMin = min(lipidZMin, atomZ)

        # Keep 0.25 nm clearance from membrane
        lipidOffset = 0.25

        upperZBoundary = (lipidZMax + lipidOffset)
        lowerZBoundary = (lipidZMin - lipidOffset)

        # ------------------------------------------------------------
        # 21. Define FINAL XY region
        #
        # Center this region on the protein center.
        # This is equivalent to:
        #
        # center +/- proteinSize/2 +/- padding
        # ------------------------------------------------------------
        offset = 0.25

        leftXboundary = (proteinCenterPos[0] - paddingSizeX / 2.0 - offset)
        rightXboundary = (proteinCenterPos[0] + paddingSizeX / 2.0 + offset)
        leftYboundary = (proteinCenterPos[1] - paddingSizeY / 2.0 - offset)
        rightYboundary = (proteinCenterPos[1] + paddingSizeY / 2.0 + offset)

        print()
        print("FINAL DELETION BOUNDARIES")
        print("X:", leftXboundary, rightXboundary)
        print("Y:", leftYboundary, rightYboundary)
        print("Z:", lowerZBoundary, upperZBoundary)

        # ------------------------------------------------------------
        # 22. DELETE WATER FROM TOPOLOGY
        # ------------------------------------------------------------
        waterToDelete = []

        for residue, pos in waterPos.items():

            waterX = pos[0]
            waterY = pos[1]
            waterZ = pos[2]

            delete_water = (
                lowerZBoundary + 1.1 < waterZ < upperZBoundary - 1.1
                or waterX < leftXboundary
                or waterX > rightXboundary
                or waterY < leftYboundary
                or waterY > rightYboundary
            )

            if delete_water:
                waterToDelete.append(residue)

        print("Water before deletion:", len(waterPos))
        print("Waters to delete:", len(waterToDelete))

        if waterToDelete:
            modeller.delete(waterToDelete)

        # ------------------------------------------------------------
        # 23. Rebuild lipid position dictionary
        #     because topology changed
        # ------------------------------------------------------------
        # lipid_to_head = {
        #     "POPC": "P",
        #     "POPE": "P",
        #     "DLPC": "P",
        #     "DLPE": "P",
        #     "DMPC": "P",
        #     "DOPC": "P",
        #     "DPPC": "P",
        # }
        lipid_to_head = {
            "POP": "P",
            "DLP": "P",
            "DMP": "P",
            "DOP": "P",
            "DPP": "P",
        }

        lipidPos = {}

        head_symbol = lipid_to_head[lipid_types_3resn[lipidType]]

        for residue in modeller.topology.residues():
            if residue.name != lipid_types_3resn[lipidType]:
                continue
            for atom in residue.atoms():
                if atom.element.symbol == head_symbol:
                    lipidPos[residue] = (modeller.positions[atom.index].value_in_unit(nanometer))
                    break

        # ------------------------------------------------------------
        # 24. DELETE LIPIDS FROM TOPOLOGY
        #
        # Use head-group coordinates to decide if a whole lipid
        # lies outside the desired membrane XY region.
        # ------------------------------------------------------------
        lipidToDelete = []

        for residue, pos in lipidPos.items():
            lipidX = pos[0]
            lipidY = pos[1]

            delete_lipid = (
                lipidX < leftXboundary
                or lipidX > rightXboundary
                or lipidY < leftYboundary
                or lipidY > rightYboundary
            )

            if delete_lipid:
                lipidToDelete.append(residue)

        print("Lipids before deletion:", len(lipidPos))
        print("Lipids to delete:", len(lipidToDelete))

        if lipidToDelete:
            modeller.delete(lipidToDelete)

        # ------------------------------------------------------------
        # 25. Rebuild water dictionary AFTER topology deletions
        # ------------------------------------------------------------
        waterPos = {}

        for residue in modeller.topology.residues():
            if residue.name in ['HOH', 'WAT']:
                for atom in residue.atoms():
                    if atom.element == elem.oxygen:
                        waterPos[residue] = (modeller.positions[atom.index])
                        break

        # Actual final number of waters
        numTotalWaters = len(waterPos)

        print("Final water count:", numTotalWaters)

        # ------------------------------------------------------------
        # 26. Set FINAL periodic box
        # ------------------------------------------------------------

        # Get the original Z length in nm
        modeller_pbc = modeller.topology.getPeriodicBoxVectors()
        z_vec = modeller_pbc[2].value_in_unit(unit.nanometer)

        # Make sure z_vec is a plain Vec3
        final_zVec = Vec3(z_vec[0], z_vec[1], z_vec[2])
        final_xVec = Vec3(paddingSizeX, 0, 0)
        final_yVec = Vec3(0, paddingSizeY, 0)

        # Apply nanometer ONCE to the complete tuple
        final_box = (final_xVec, final_yVec, final_zVec) * unit.nanometer

        modeller.topology.setPeriodicBoxVectors(final_box)

        print("FINAL BOX:")
        print(modeller.topology.getPeriodicBoxVectors())

        # ------------------------------------------------------------
        # 27. Update self ONLY NOW
        # ------------------------------------------------------------
        self.topology = modeller.topology
        self.positions = modeller.positions

        # Re-create residue templates for current topology
        newResidueTemplates = {}

        for r1, r2 in zip(self.topology.residues(), modeller.topology.residues()):

            if r1 in residueTemplates:
                newResidueTemplates[r2] = (residueTemplates[r1])

        # ------------------------------------------------------------
        # 28. Write structure before ions
        # ------------------------------------------------------------
        if write_structure:

            with open("addMembrane_sol.pdb", "w") as f:
                PDBFile.writeFile(self.topology, self.positions, f)

        # ------------------------------------------------------------
        # 29. Add ions
        # ------------------------------------------------------------
        self._addIons(
            forcefield,
            numTotalWaters,
            waterPos,
            positiveIon=positiveIon,
            negativeIon=negativeIon,
            ionicStrength=ionicStrength,
            neutralize=neutralize,
            residueTemplates=newResidueTemplates
        )

        # ------------------------------------------------------------
        # 30. Write final structure
        # ------------------------------------------------------------
        if write_structure:

            with open("addMembrane_sol_ion.pdb", "w") as f:
                PDBFile.writeFile(self.topology, self.positions, f)