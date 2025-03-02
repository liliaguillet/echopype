import numpy as np
import pandas as pd
import pytest
from scipy.io import loadmat
import echopype as ep
from echopype.calibrate.env_params_old import EnvParams
import xarray as xr


@pytest.fixture
def azfp_path(test_path):
    return test_path['AZFP']


@pytest.fixture
def ek60_path(test_path):
    return test_path['EK60']


@pytest.fixture
def ek80_path(test_path):
    return test_path['EK80']


@pytest.fixture
def ek80_cal_path(test_path):
    return test_path['EK80_CAL']


@pytest.fixture
def ek80_ext_path(test_path):
    return test_path['EK80_EXT']


def test_compute_Sv_returns_water_level(ek60_path):

    # get EchoData object that has the water_level variable under platform and compute Sv of it
    ed = ep.open_raw(ek60_path / "ncei-wcsd" / "Summer2017-D20170620-T011027.raw", "EK60")
    ds_Sv = ep.calibrate.compute_Sv(ed)

    # make sure the returned Dataset has water_level and throw an assertion error if the
    # EchoData object does not have water_level (just in case we remove it from the file
    # used in the future)
    assert 'water_level' in ed["Platform"].data_vars.keys()
    assert 'water_level' in ds_Sv.data_vars


def test_compute_Sv_ek60_echoview(ek60_path):
    # constant range_sample
    ek60_raw_path = str(
        ek60_path.joinpath('DY1801_EK60-D20180211-T164025.raw')
    )
    ek60_echoview_path = ek60_path.joinpath('from_echoview')

    # Convert file
    echodata = ep.open_raw(ek60_raw_path, sonar_model='EK60')

    # Calibrate to get Sv
    ds_Sv = ep.calibrate.compute_Sv(echodata)

    # Compare with EchoView outputs
    channels = []
    for freq in [18, 38, 70, 120, 200]:
        fname = str(
            ek60_echoview_path.joinpath(
                'DY1801_EK60-D20180211-T164025-Sv%d.csv' % freq
            )
        )
        channels.append(
            pd.read_csv(fname, header=None, skiprows=[0]).iloc[:, 13:]
        )
    test_Sv = np.stack(channels)

    # Echoview data is shifted by 1 sample along range (missing the first sample)
    # TODO: resolve: pydevd warning: Computing repr of channels (list) was slow (took 0.29s)
    assert np.allclose(
        test_Sv[:, :, 7:],
        ds_Sv.Sv.isel(ping_time=slice(None, 10), range_sample=slice(8, None)),
        atol=1e-8
    )


def test_compute_Sv_ek60_matlab(ek60_path):
    ek60_raw_path = str(
        ek60_path.joinpath('DY1801_EK60-D20180211-T164025.raw')
    )
    ek60_matlab_path = str(
        ek60_path.joinpath('from_matlab', 'DY1801_EK60-D20180211-T164025.mat')
    )

    # Convert file
    echodata = ep.open_raw(ek60_raw_path, sonar_model='EK60')

    # Calibrate to get Sv
    ds_Sv = ep.calibrate.compute_Sv(echodata)
    ds_TS = ep.calibrate.compute_TS(echodata)

    # Load matlab outputs and test

    # matlab outputs were saved using
    #   save('from_matlab/DY1801_EK60-D20180211-T164025.mat', 'data')
    ds_base = loadmat(ek60_matlab_path)

    def check_output(da_cmp, cal_type):
        # ds_base["data"]["pings"][0][0]["Sv"].shape = (1, 5)  [5 channels]
        for seq, ch in enumerate(ds_base["data"]["config"][0][0]["channelid"][0]):
            ep_vals = da_cmp.sel(channel=ch).squeeze().data[:, 8:]  # ignore the first 8 samples
            pyel_vals = ds_base['data']['pings'][0][0][cal_type][0, seq].T[:, 8:]
            assert np.allclose(pyel_vals, ep_vals)

    # Check Sv
    check_output(ds_Sv['Sv'], 'Sv')

    # Check TS
    check_output(ds_TS['TS'], 'Sp')


def test_compute_Sv_ek60_duplicated_freq(ek60_path):

    # TODO: add comparison of actual values in this test

    ek60_raw_path = str(
        ek60_path.joinpath('DY1002_EK60-D20100318-T023008_rep_freq.raw')
    )

    # Convert file
    echodata = ep.open_raw(ek60_raw_path, sonar_model='EK60')

    # Calibrate to get Sv
    ds_Sv = ep.calibrate.compute_Sv(echodata)
    ds_TS = ep.calibrate.compute_TS(echodata)

    assert isinstance(ds_Sv, xr.Dataset)
    assert isinstance(ds_TS, xr.Dataset)


def test_compute_Sv_azfp(azfp_path):
    azfp_01a_path = str(azfp_path.joinpath('17082117.01A'))
    azfp_xml_path = str(azfp_path.joinpath('17041823.XML'))
    azfp_matlab_Sv_path = str(
        azfp_path.joinpath('from_matlab', '17082117_matlab_Output_Sv.mat')
    )
    azfp_matlab_TS_path = str(
        azfp_path.joinpath('from_matlab', '17082117_matlab_Output_TS.mat')
    )

    # Convert to .nc file
    echodata = ep.open_raw(
        raw_file=azfp_01a_path, sonar_model='AZFP', xml_path=azfp_xml_path
    )

    # Calibrate using identical env params as in Matlab ParametersAZFP.m
    # AZFP Matlab code uses average temperature
    avg_temperature = (
        echodata["Environment"]['temperature'].mean('time1').values
    )
    env_params = {
        'temperature': avg_temperature,
        'salinity': 27.9,
        'pressure': 59,
    }

    ds_Sv = ep.calibrate.compute_Sv(echodata=echodata, env_params=env_params)
    ds_TS = ep.calibrate.compute_TS(echodata=echodata, env_params=env_params)

    # Load matlab outputs and test
    # matlab outputs were saved using
    #   save('from_matlab/17082117_matlab_Output.mat', 'Output')  # data variables
    #   save('from_matlab/17082117_matlab_Par.mat', 'Par')  # parameters

    def check_output(base_path, ds_cmp, cal_type):
        ds_base = loadmat(base_path)
        # print(f"ds_base = {ds_base}")
        cal_type_in_ds_cmp = {
            'Sv': 'Sv',
            'TS': 'TS',  # TS here is TS in matlab outputs
        }
        for fidx in range(4):  # loop through all freq
            assert np.alltrue(
                ds_cmp.echo_range.isel(channel=fidx, ping_time=0).values[None, :]
                == ds_base['Output'][0]['Range'][fidx]
            )
            assert np.allclose(
                ds_cmp[cal_type_in_ds_cmp[cal_type]].isel(channel=fidx).values,
                ds_base['Output'][0][cal_type][fidx],
                atol=1e-13,
                rtol=0,
            )

    # Check Sv
    check_output(base_path=azfp_matlab_Sv_path, ds_cmp=ds_Sv, cal_type='Sv')

    # Check TS
    check_output(base_path=azfp_matlab_TS_path, ds_cmp=ds_TS, cal_type='TS')


def test_compute_Sv_ek80_CW_complex(ek80_path):
    """Test calibrate CW mode data encoded as complex samples."""
    ek80_raw_path = str(
        ek80_path.joinpath('ar2.0-D20201210-T000409.raw')
    )  # CW complex
    echodata = ep.open_raw(ek80_raw_path, sonar_model='EK80')
    ds_Sv = ep.calibrate.compute_Sv(
        echodata, waveform_mode='CW', encode_mode='complex'
    )
    assert isinstance(ds_Sv, xr.Dataset) is True
    ds_TS = ep.calibrate.compute_TS(
        echodata, waveform_mode='CW', encode_mode='complex'
    )
    assert isinstance(ds_TS, xr.Dataset) is True


def test_compute_Sv_ek80_BB_complex(ek80_path):
    """Test calibrate BB mode data encoded as complex samples."""
    ek80_raw_path = str(
        ek80_path.joinpath('ar2.0-D20201209-T235955.raw')
    )  # CW complex
    echodata = ep.open_raw(ek80_raw_path, sonar_model='EK80')
    ds_Sv = ep.calibrate.compute_Sv(
        echodata, waveform_mode='BB', encode_mode='complex'
    )
    assert isinstance(ds_Sv, xr.Dataset) is True
    ds_TS = ep.calibrate.compute_TS(
        echodata, waveform_mode='BB', encode_mode='complex'
    )
    assert isinstance(ds_TS, xr.Dataset) is True


def test_compute_Sv_ek80_CW_power_BB_complex(ek80_path):
    """
    Tests calibration in CW mode data encoded as power samples
    and calibration in BB mode data encoded as complex samples,
    while the file contains both CW power and BB complex samples.
    """
    ek80_raw_path = ek80_path / "Summer2018--D20180905-T033113.raw"
    ed = ep.open_raw(ek80_raw_path, sonar_model="EK80")
    ds_Sv = ep.calibrate.compute_Sv(
        ed, waveform_mode="CW", encode_mode="power"
    )
    assert isinstance(ds_Sv, xr.Dataset)
    ds_Sv = ep.calibrate.compute_Sv(
        ed, waveform_mode="BB", encode_mode="complex"
    )
    assert isinstance(ds_Sv, xr.Dataset)


def test_compute_Sv_ek80_CW_complex_BB_complex(ek80_cal_path, ek80_path):
    """
    Tests calibration for file containing both BB and CW mode data
    with both encoded as complex samples.
    """
    ek80_raw_path = ek80_cal_path / "2018115-D20181213-T094600.raw"  # rx impedance / rx fs / tcvr type
    # ek80_raw_path = ek80_path / "D20170912-T234910.raw"  # rx impedance / rx fs / tcvr type
    # ek80_raw_path = ek80_path / "Summer2018--D20180905-T033113.raw"  # BB only, rx impedance / rx fs / tcvr type
    # ek80_raw_path = ek80_path / "ar2.0-D20201210-T000409.raw"  # CW only, rx impedance / rx fs / tcvr type
    # ek80_raw_path = ek80_path / "saildrone/SD2019_WCS_v05-Phase0-D20190617-T125959-0.raw"  # rx impedance / tcvr type
    # ek80_raw_path = ek80_path / "D20200528-T125932.raw"  # CW only,  WBT MINI, rx impedance / rx fs / tcvr type
    ed = ep.open_raw(ek80_raw_path, sonar_model="EK80")
    # ds_Sv = ep.calibrate.compute_Sv(
    #     ed, waveform_mode="CW", encode_mode="complex"
    # )
    # assert isinstance(ds_Sv, xr.Dataset)
    ds_Sv = ep.calibrate.compute_Sv(
        ed, waveform_mode="BB", encode_mode="complex"
    )
    assert isinstance(ds_Sv, xr.Dataset)


def test_env_params(ek60_path):
    """
    Tests EnvParams interpolation
    """

    ed = ep.open_raw(ek60_path / "ncei-wcsd" / "Summer2017-D20170620-T011027.raw", "EK60")

    # stationary
    # since the raw ping_times go up to 1:43 but the env_params ping_time stops at 1:25,
    # values after 1:25 will be extrapolated
    env_params_data = xr.Dataset(
        data_vars={
            "pressure": ("time3", np.arange(50)),
            "salinity": ("time3", np.arange(50)),
            "temperature": ("time3", np.arange(50)),
        },
        coords={
            "time3": np.arange("2017-06-20T01:00", "2017-06-20T01:25", np.timedelta64(30, "s"), dtype="datetime64[ns]")
        }
    )
    env_params = EnvParams(env_params_data, "stationary")
    converted_env_params = env_params._apply(ed)
    for var in converted_env_params.values():
        assert np.all(np.diff(var) > 0)
        assert np.all(0 <= var)
        assert np.all(var < 100)
    # TODO: substitute ping_time and input values of the env variables
    #       so that interpolation gives nice outputs
    known_values = {
        "temperature": {
            "2017-06-20T01:10:27.136999936": 20.904566664533334,
            "2017-06-20T01:10:28.149000192": 20.9383000064,
            "2017-06-20T01:10:29.160999936": 20.9720333312,
            "2017-06-20T01:10:30.174000128": 21.005800004266668,
            "2017-06-20T01:10:31.184999936": 21.039499997866667,
            "2017-06-20T01:42:56.995999744": 85.89986665813333,
            "2017-06-20T01:42:58.008999936": 85.9336333312,
            "2017-06-20T01:42:59.020000256": 85.96733334186666,
            "2017-06-20T01:43:00.032000000": 86.00106666666667,
            "2017-06-20T01:43:01.045000192": 86.03483333973334,
        },
        "salinity": {
            "2017-06-20T01:10:27.136999936": 20.904566664533334,
            "2017-06-20T01:10:28.149000192": 20.9383000064,
            "2017-06-20T01:10:29.160999936": 20.9720333312,
            "2017-06-20T01:10:30.174000128": 21.005800004266668,
            "2017-06-20T01:10:31.184999936": 21.039499997866667,
            "2017-06-20T01:42:56.995999744": 85.89986665813333,
            "2017-06-20T01:42:58.008999936": 85.9336333312,
            "2017-06-20T01:42:59.020000256": 85.96733334186666,
            "2017-06-20T01:43:00.032000000": 86.00106666666667,
            "2017-06-20T01:43:01.045000192": 86.0348333397333,
        },
        "pressure": {
            "2017-06-20T01:10:27.136999936": 20.904566664533334,
            "2017-06-20T01:10:28.149000192": 20.9383000064,
            "2017-06-20T01:10:29.160999936": 20.9720333312,
            "2017-06-20T01:10:30.174000128": 21.005800004266668,
            "2017-06-20T01:10:31.184999936": 21.039499997866667,
            "2017-06-20T01:42:56.995999744": 85.89986665813333,
            "2017-06-20T01:42:58.008999936": 85.9336333312,
            "2017-06-20T01:42:59.020000256": 85.96733334186666,
            "2017-06-20T01:43:00.032000000": 86.00106666666667,
            "2017-06-20T01:43:01.045000192": 86.03483333973334,
        }
    }
    for var, values in known_values.items():
        for time, value in values.items():
            assert np.isclose(converted_env_params[var].sel(time1=time), value)

    # mobile
    rng = np.random.default_rng(0)
    env_params_data = xr.Dataset(
        data_vars={
            "pressure": ("time", np.arange(100)),
            "salinity": ("time", np.arange(100)),
            "temperature": ("time", np.arange(100)),
        },
        coords={
            "latitude": ("time", rng.random(size=100) + 44),
            "longitude": ("time", rng.random(size=100) - 125),
        }
    )
    env_params = EnvParams(env_params_data, "mobile")
    converted_env_params = env_params._apply(ed)
    for var in converted_env_params.values():
        assert np.all(0 <= var[~np.isnan(var)])
        assert np.all(var[~np.isnan(var)] < 100)
    known_values = {
        "temperature": {
            "2017-06-20T01:10:27.136999936":  np.nan,
            "2017-06-20T01:10:28.149000192":  72.57071056437047,
            "2017-06-20T01:10:29.160999936":  72.56164311204404,
            "2017-06-20T01:10:30.174000128":  72.5641609908268,
            "2017-06-20T01:10:31.184999936":  72.5540675620769,
            "2017-06-20T01:42:56.995999744":  64.78639664394186,
            "2017-06-20T01:42:58.008999936":  64.76543272189699,
            "2017-06-20T01:42:59.020000256":  64.77890258158483,
            "2017-06-20T01:43:00.032000000":  64.76186093048929,
            "2017-06-20T01:43:01.045000192":  64.76763007606817,
        },
        "salinity": {
            "2017-06-20T01:10:27.136999936":  np.nan,
            "2017-06-20T01:10:28.149000192":  72.57071056437047,
            "2017-06-20T01:10:29.160999936":  72.56164311204404,
            "2017-06-20T01:10:30.174000128":  72.5641609908268,
            "2017-06-20T01:10:31.184999936":  72.5540675620769,
            "2017-06-20T01:42:56.995999744":  64.78639664394186,
            "2017-06-20T01:42:58.008999936":  64.76543272189699,
            "2017-06-20T01:42:59.020000256":  64.77890258158483,
            "2017-06-20T01:43:00.032000000":  64.76186093048929,
            "2017-06-20T01:43:01.045000192":  64.76763007606817,
        },
        "pressure": {
            "2017-06-20T01:10:27.136999936": np.nan,
            "2017-06-20T01:10:28.149000192": 72.57071056437047,
            "2017-06-20T01:10:29.160999936": 72.56164311204404,
            "2017-06-20T01:10:30.174000128": 72.5641609908268,
            "2017-06-20T01:10:31.184999936": 72.5540675620769,
            "2017-06-20T01:42:56.995999744": 64.78639664394186,
            "2017-06-20T01:42:58.008999936": 64.76543272189699,
            "2017-06-20T01:42:59.020000256": 64.77890258158483,
            "2017-06-20T01:43:00.032000000": 64.76186093048929,
            "2017-06-20T01:43:01.045000192": 64.76763007606817,
        },
    }
    for var, values in known_values.items():
        for time, value in values.items():
            print(var, time, value)
            assert np.isnan(value) or np.isclose(converted_env_params[var].sel(time1=time), value)
