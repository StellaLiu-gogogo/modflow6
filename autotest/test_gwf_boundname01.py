import os

import flopy
import numpy as np
import pytest
from framework import TestFramework
from simulation import TestSimulation

ex = [
    "bndname01",
]


def build_model(idx, exdir):

    sim = get_model(idx, exdir)

    ws = os.path.join(exdir, "mf6")
    mc = get_model(idx, ws)

    return sim, mc


def get_model(idx, ws):

    nlay, nrow, ncol = 1, 1, 100
    nper = 1
    perlen = [5.0]
    nstp = [1]
    tsmult = [1.0]
    delr = 1.0
    delc = 1.0
    top = 1.0
    laytyp = 0
    botm = [0.0]
    strt = 1.0
    hk = 1.0

    boundnames = ('left face"s', "right face")
    c = {
        0: [
            [0, 0, 0, 1.0000000, boundnames[0]],
            [0, 0, 99, 0.0000000, boundnames[1]],
        ]
    }

    nouter, ninner = 100, 300
    hclose, rclose, relax = 1e-6, 1e-6, 1.0

    tdis_rc = []
    for i in range(nper):
        tdis_rc.append((perlen[i], nstp[i], tsmult[i]))

    name = ex[idx]

    # build MODFLOW 6 files
    sim = flopy.mf6.MFSimulation(
        sim_name=name, version="mf6", exe_name="mf6", sim_ws=ws
    )
    # create tdis package
    tdis = flopy.mf6.ModflowTdis(
        sim, time_units="DAYS", nper=nper, perioddata=tdis_rc
    )

    # create iterative model solution and register
    imsgwf = flopy.mf6.ModflowIms(
        sim,
        print_option="SUMMARY",
        outer_dvclose=hclose,
        outer_maximum=nouter,
        under_relaxation="NONE",
        inner_maximum=ninner,
        inner_dvclose=hclose,
        rcloserecord=rclose,
        linear_acceleration="CG",
        scaling_method="NONE",
        reordering_method="NONE",
        relaxation_factor=relax,
    )

    # create gwf model
    gwfname = "gwf_" + name
    gwf = flopy.mf6.ModflowGwf(
        sim,
        modelname=gwfname,
        save_flows=True,
    )

    dis = flopy.mf6.ModflowGwfdis(
        gwf,
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=delr,
        delc=delc,
        top=top,
        botm=botm,
        idomain=np.ones((nlay, nrow, ncol), dtype=int),
    )

    # initial conditions
    ic = flopy.mf6.ModflowGwfic(
        gwf,
        strt=strt,
    )

    # node property flow
    npf = flopy.mf6.ModflowGwfnpf(
        gwf, save_specific_discharge=True, icelltype=laytyp, k=hk, k33=hk
    )

    # chd files
    chd = flopy.mf6.ModflowGwfchd(
        gwf,
        print_input=True,
        boundnames=True,
        maxbound=len(c),
        stress_period_data=c,
        save_flows=False,
        print_flows=True,
        pname="CHD-1",
    )
    fname = f"{gwfname}.chd.obs"
    chd_obs = {
        f"{fname}.csv": [
            (boundnames[0], "chd", boundnames[0]),
            (boundnames[1], "chd", boundnames[1]),
        ]
    }
    chd.obs.initialize(filename=fname, print_input=True, continuous=chd_obs)

    # output control
    oc = flopy.mf6.ModflowGwfoc(
        gwf,
        budget_filerecord=f"{gwfname}.cbc",
        head_filerecord=f"{gwfname}.hds",
        headprintrecord=[("COLUMNS", 10, "WIDTH", 15, "DIGITS", 6, "GENERAL")],
        saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
        printrecord=[("HEAD", "LAST"), ("BUDGET", "LAST")],
    )

    return sim


def replace_quotes(idx, exdir):
    ws = os.path.join(exdir, "mf6")
    gwfname = f"gwf_{ex[idx]}"
    extensions = (".chd", ".chd.obs")
    for ext in extensions:
        fpth = os.path.join(ws, f"{gwfname}{ext}")
        with open(fpth) as f:
            lines = f.readlines()
        with open(fpth, "w") as f:
            for line in lines:
                f.write(line.replace("'", '"').replace('face"s', "face's"))


def eval_obs(sim):
    print("evaluating observations results..." f"({sim.name})")

    fpth = os.path.join(sim.simpath, f"gwf_{sim.name}.chd.obs.csv")
    obs0 = np.genfromtxt(fpth, delimiter=",", names=True)
    names0 = obs0.dtype.names

    fpth = os.path.join(sim.simpath, "mf6", f"gwf_{sim.name}.chd.obs.csv")
    obs1 = np.genfromtxt(fpth, delimiter=",", names=True)
    names1 = obs1.dtype.names

    assert names0 == names1, "observation names are not identical"
    assert np.array_equal(obs0, obs1), "observations are not identical"


@pytest.mark.parametrize(
    "idx, name",
    list(enumerate(ex)),
)
def test_mf6model(idx, name, function_tmpdir, targets):
    test = TestFramework()
    test.build(build_model, 0, str(function_tmpdir))
    test.run(
        TestSimulation(name=name, exe_dict=targets, idxsim=0),
        str(function_tmpdir),
    )
