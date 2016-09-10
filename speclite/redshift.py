# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Apply redshift transformations to wavelength, flux, inverse variance, etc.

Attributes
----------
exponents : dict

    Dictionary of predefined array names and corresponding redshift exponents,
    used by :func:`transform` to automatically select the correct exponent.
"""
from __future__ import print_function, division

import collections

import numpy as np
import numpy.ma as ma

import speclite.utility


exponents = dict(
    wlen=+1, wavelength=+1, wavelength_error=+1,
    freq=-1, frequency=-1, frequency_error=-1,
    flux=-1, irradiance_per_wavelength=-1,
    irradiance_per_frequency=+1,
    ivar=+2, ivar_irradiance_per_wavelength=+2,
    ivar_irradiance_per_frequency=-2)


def apply_redshift_transform(z_in, z_out, data_in, data_out, exponent):
    """Apply a redshift transform to spectroscopic quantities.

    The input redshifts can either be scalar values or arrays.  If either is
    an array, the result will be broadcast using their shapes.

    Parameters
    ----------
    z_in : float or numpy.ndarray
        Redshift(s) of the input spectral data, which must all be > -1.
    z_out : float or numpy.ndarray
        Redshift(s) of the output spectral data, which must all be > -1.
    data_in : dict
        Dictionary of numpy-compatible arrays of input quantities to transform.
        Usually obtained using :func:`speclite.utility.prepare_data`.
    data_out : dict
        Dictionary of numpy-compatible arrays to fill with transformed values.
        Usually obtained using :func:`speclite.utility.prepare_data`.
        The names used here must be a subset of the names appearing in
        data_in.
    exponent : dict
        Dictionary of exponents :math:`n` to use in the factor that
        transforms each input array:

        .. math::

            \left(\\frac{1 + z_{out}}{1 + z_{in}}\\right)^n

        Any names appearing in data_out that are not included here will be
        passed through unchanged.
    """
    # Calculate the redshift multiplicative factor, which might have a
    # non-trivial shape if either z_in or z_out is an array.
    z_in = np.asarray(z_in)
    z_out = np.asarray(z_out)
    if np.any(z_in <= -1):
        raise ValueError('Found invalid z_in <= -1.')
    if np.any(z_out <= -1):
        raise ValueError('Found invalid z_out <= -1.')
    zfactor = (1. + z_out) / (1. + z_in)

    # Fill data_out with transformed arrays.
    for name in data_out:
        n = exponent.get(name, 0)
        if n != 0:
            data_out[name][:] = data_in[name] * zfactor ** exponent[name]
        # This condition is not exhaustive but avoids an un-necessary copy
        # in the most comment case that data_out[name] is a direct view
        # of data_in[name].
        elif not (data_out[name].base is data_in[name]):
            data_out[name][:] = data_in[name]

    return data_out


def redshift_array(z_in, z_out, y_in, y_out=None, exponent=None, name='y'):
    """Redshift a single array.

    The result is calculated as::

        y_out = y_in * ((1. + z_out) / (1. + z_in)) ** exponent

    If either of z_in or z_out is an array, the result will be calculated
    following the usual broadcasting rules and may result in y_out having a
    different shape from y_in.

    The :func:`redshift` function provides a convenient wrapper for transforming
    each column of a tabular object like a numpy structured array or an
    astropy table.

    Parameters
    ----------
    z_in : number or array
        Redshift(s) of the input spectral data, which must all be > -1.
    z_out : float or numpy.ndarray
        Redshift(s) of the output spectral data, which must all be > -1.
    y_in : array
        Array of input y values to transform.  Values must be numeric and
        finite (but invalid values can be masked).
    y_out : numpy array or None
        Array where output values should be written.  If None is specified
        an appropriate array will be created.  If y_out is the same object
        as y_in, the redshift transform is performed in place.
    name : str
        Name associated with y to include in any exception message.

    Returns
    -------
    numpy array
        An array of redshifted values.  The output shape will be the result
        of broadcasting the inputs.
    """
    z_in = np.asanyarray(z_in)
    z_out = np.asanyarray(z_out)
    if np.any(z_in <= -1):
        raise ValueError('Found invalid z_in <= -1.')
    if np.any(z_out <= -1):
        raise ValueError('Found invalid z_out <= -1.')

    y_in = np.asanyarray(y_in)
    if not np.issubdtype(y_in.dtype, np.number):
        raise ValueError(
            'Cannot redshift non-numeric values for {0}.'.format(name))
    if not np.all(np.isfinite(y_in)):
        raise ValueError(
            'Cannot redshift non-finite values for {0}.'.format(name))

    # Use the name to set the exponent if not already set.
    if exponent is None and name in exponents:
        exponent = exponents[name]
    if exponent is None:
        exponent = 0.

    # We always broadcast even when exponent is None or zero.
    try:
        shape_out = np.broadcast(z_in, z_out, y_in).shape
    except ValueError:
        raise ValueError('Cannot broadcast {0} with shapes {1}, {2}, {3}.'
                         .format(name, z_in.shape, z_out.shape, y_in.shape))

    if y_out is None:
        # Create a new output array.
        y_out = speclite.utility.empty_like(y_in, shape_out, y_in.dtype)
    else:
        # Check that the array provided has the required properties.
        if y_out.shape != shape_out:
            raise ValueError('Wrong output shape {0} for {1}.'
                             .format(y_out.shape, name))
        if y_out.dtype != y_in.dtype:
            raise ValueError('Wrong output dtype {0} for {1}.'
                             .format(y_out.dtype, name))

    # This will broadcast correctly, even when exponent is zero.
    y_out[:] = y_in * ((1. + z_out) / (1. + z_in)) ** exponent

    return y_out


def redshift(*args, **kwargs):
    """Perform redshift transforms of the columns of a tabular object.

    The exponents used to transform each column are inferred from the
    column names, which must be listed in :data:`redshift.exponents`.

    >>> wlen0 = np.arange(4000., 10000.)
    >>> flux0 = np.ones(wlen0.shape)
    >>> result = transform(z_in=0, z_out=1, wlen=wlen0, flux=flux0)
    >>> wlen, flux = result['wlen'], result['flux']
    >>> flux[:5]
    array([ 0.5,  0.5,  0.5,  0.5,  0.5])

    Uses :function:`redshift_array` to transform each column.

    Parameters
    ----------
    *args : list
        Arguments specifying the arrays to transform and passed to
        :func:`speclite.utility.prepare_data`.
    **kwargs : dict
        Arguments specifying the arrays to transform and passed to
        :func:`speclite.utility.prepare_data`, after filtering out the
        keywords listed below.
    z : float or numpy.ndarray or None
        Redshift(s) of the output spectra data, which must all be > -1.
        An input redshift of zero is assumed.  Cannot be combined with
        z_in or z_out.
    z_in : float or numpy.ndarray or None
        Redshift(s) of the input spectral data, which must all be > -1.
        When specified, z_out must also be specified. Cannot be combined
        with the z parameter.
    z_out : float or numpy.ndarray or None
        Redshift(s) of the output spectral data, which must all be > -1.
        When specified, z_in must also be specified. Cannot be combined
        with the z parameter.
    data_out : tabular object or None
        When the input data is a tabular object, use this parameter to specify
        where the the results should be stored.  If None, then an appropriate
        result object will be created.  Set equal to the input tabular object
        to perform transforms in place.  Must be of the same type as the input
        data and appropriately sized for the requested calculation, including
        any broadcasting.

    Returns
    -------
    tabular or dict
        A tabular object (astropy table or numpy structured array) matching
        the input type, or else a dictionary of numpy arrays if the input
        consists of arrays passed as keyword arguments.

    Raises
    ------
    ValueError
        Cannot perform redshift in place when broadcasting or invalid
        combination of z, z_in, z_out options.
    """
    kwargs, options = speclite.utility.get_options(
        kwargs, z=None, z_in=None, z_out=None, data_out=None)

    # Combine the z, z_in, z_out options.
    if options['z'] is not None:
        if options['z_in'] is not None or options['z_out'] is not None:
            raise ValueError('Cannot combine z parameter with z_in, z_out.')
        z_in = 0
        z_out = options['z']
    elif options['z_in'] is None or options['z_out'] is None:
        raise ValueError('Must both z_in and z_out.')
    else:
        z_in = options['z_in']
        z_out = options['z_out']

    # Prepare the input columns to transform.
    arrays_in, data_in = speclite.utility.prepare_data(
        'read_only', args, kwargs)

    # Prepare the output columns to fill, if data_out is specified.
    if options['data_out'] is not None:
        arrays_out, data_out = speclite.utility.prepare_data(
            'in_place', [options['data_out']], {})
    else:
        arrays_out = collections.OrderedDict()
        data_out = None

    for name in arrays_in:
        if data_out is None:
            y_out = None
        else:
            # All output arrays should be present in arrays_out.
            if name not in arrays_out:
                raise ValueError('data_out missing required column {0}.'
                                 .format(name))
            y_out = arrays_out[name]
        arrays_out[name] = redshift_array(
            z_in, z_out, arrays_in[name], y_out, name=name)

    if data_out is None:
        data_out = speclite.utility.tabular_like(data_in, arrays_out)

    print('arrays_out', arrays_out)
    print('data_in', data_in)
    print('data_out', data_out)

    return data_out
