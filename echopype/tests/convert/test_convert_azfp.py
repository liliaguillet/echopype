"""test_convert_azfp.py

This module contains tests that:
- verify echopype converted files against those from AZFP Matlab scripts and EchoView
- convert AZFP file with different range settings across frequency
"""

import numpy as np
import pandas as pd
from scipy.io import loadmat
from echopype import open_raw
import pytest


@pytest.fixture
def azfp_path(test_path):
    return test_path["AZFP"]

def check_platform_required_vars(echodata):
    # check convention-required variables in the Platform group
    for var in [
        "MRU_offset_x",
        "MRU_offset_y",
        "MRU_offset_z",
        "MRU_rotation_x",
        "MRU_rotation_y",
        "MRU_rotation_z",
        "position_offset_x",
        "position_offset_y",
        "position_offset_z",
        "transducer_offset_x",
        "transducer_offset_y",
        "transducer_offset_z",
        "vertical_offset",
        "water_level",
    ]:
        assert var in echodata["Platform"]
        assert np.isnan(echodata["Platform"][var])


def test_convert_azfp_01a_matlab_raw(azfp_path):
    """Compare parsed raw data with Matlab outputs."""
    azfp_01a_path = str(azfp_path.joinpath('17082117.01A'))
    azfp_xml_path = str(azfp_path.joinpath('17041823.XML'))
    azfp_matlab_data_path = str(
        azfp_path.joinpath('from_matlab', '17082117_matlab_Data.mat')
    )
    azfp_matlab_output_path = str(
        azfp_path.joinpath('from_matlab', '17082117_matlab_Output_Sv.mat')
    )

    # Convert file
    echodata = open_raw(
        raw_file=azfp_01a_path, sonar_model='AZFP', xml_path=azfp_xml_path
    )

    # Read in the dataset that will be used to confirm working conversions. (Generated by Matlab)
    ds_matlab = loadmat(azfp_matlab_data_path)
    ds_matlab_output = loadmat(azfp_matlab_output_path)

    # Test beam group
    # frequency
    assert np.array_equal(
        ds_matlab['Data']['Freq'][0][0].squeeze(),
        echodata["Sonar/Beam_group1"].frequency_nominal / 1000,
    )  # matlab file in kHz
    # backscatter count
    assert np.array_equal(
        np.array(
            [ds_matlab_output['Output'][0]['N'][fidx] for fidx in range(4)]
        ),
        echodata["Sonar/Beam_group1"].backscatter_r.isel(beam=0).drop('beam').values,
    )

    # Test vendor group
    # Test temperature
    assert np.array_equal(
        np.array([d[4] for d in ds_matlab['Data']['Ancillary'][0]]).squeeze(),
        echodata["Vendor_specific"].ancillary.isel(ancillary_len=4).values,
    )
    assert np.array_equal(
        np.array([d[0] for d in ds_matlab['Data']['BatteryTx'][0]]).squeeze(),
        echodata["Vendor_specific"].battery_tx,
    )
    assert np.array_equal(
        np.array(
            [d[0] for d in ds_matlab['Data']['BatteryMain'][0]]
        ).squeeze(),
        echodata["Vendor_specific"].battery_main,
    )
    # tilt x-y
    assert np.array_equal(
        np.array([d[0] for d in ds_matlab['Data']['Ancillary'][0]]).squeeze(),
        echodata["Vendor_specific"].tilt_x_count,
    )
    assert np.array_equal(
        np.array([d[1] for d in ds_matlab['Data']['Ancillary'][0]]).squeeze(),
        echodata["Vendor_specific"].tilt_y_count,
    )

    # check convention-required variables in the Platform group
    check_platform_required_vars(echodata)


def test_convert_azfp_01a_matlab_derived():
    """Compare variables derived from raw parsed data with Matlab outputs."""
    # TODO: test derived data
    #  - ds_beam.ping_time from 01A raw data records
    #  - investigate why ds_beam.tilt_x/y are different from ds_matlab['Data']['Tx']/['Ty']
    #  - derived temperature

    # # check convention-required variables in the Platform group
    # check_platform_required_vars(echodata)

    pytest.xfail("Tests for converting AZFP and comparing it"
                 + " against Matlab derived data have not been implemented yet.")


def test_convert_azfp_01a_raw_echoview(azfp_path):
    """Compare parsed power data (count) with csv exported by EchoView."""
    azfp_01a_path = str(azfp_path.joinpath('17082117.01A'))
    azfp_xml_path = str(azfp_path.joinpath('17041823.XML'))

    # Read csv files exported by EchoView
    azfp_csv_path = [
        azfp_path.joinpath('from_echoview', '17082117-raw%d.csv' % freq)
        for freq in [38, 125, 200, 455]
    ]
    channels = []
    for file in azfp_csv_path:
        channels.append(
            pd.read_csv(file, header=None, skiprows=[0]).iloc[:, 6:]
        )
    test_power = np.stack(channels)

    # Convert to netCDF and check
    echodata = open_raw(
        raw_file=azfp_01a_path, sonar_model='AZFP', xml_path=azfp_xml_path
    )
    assert np.array_equal(test_power, echodata["Sonar/Beam_group1"].backscatter_r.isel(beam=0).drop('beam'))

    # check convention-required variables in the Platform group
    check_platform_required_vars(echodata)


def test_convert_azfp_01a_different_ranges(azfp_path):
    """Test converting files with different range settings across frequency."""
    azfp_01a_path = str(azfp_path.joinpath('17031001.01A'))
    azfp_xml_path = str(azfp_path.joinpath('17030815.XML'))

    # Convert file
    echodata = open_raw(
        raw_file=azfp_01a_path, sonar_model='AZFP', xml_path=azfp_xml_path
    )
    assert echodata["Sonar/Beam_group1"].backscatter_r.sel(channel='55030-125-1').dropna(
        'range_sample'
    ).shape == (360, 438, 1)
    assert echodata["Sonar/Beam_group1"].backscatter_r.sel(channel='55030-769-4').dropna(
        'range_sample'
    ).shape == (360, 135, 1)

    # check convention-required variables in the Platform group
    check_platform_required_vars(echodata)
