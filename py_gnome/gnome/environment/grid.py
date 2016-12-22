"""
grid for wind or current data
"""

import copy

import numpy as np

from colander import (SchemaNode, drop, Float, String, SequenceSchema, Sequence)

from gnome.cy_gnome.cy_grid_curv import CyTimeGridWindCurv
from gnome.cy_gnome.cy_grid_rect import CyTimeGridWindRect
from gnome.utilities.time_utils import date_to_sec
from gnome.utilities.serializable import Serializable, Field
from gnome.persist import base_schema

from .environment import Environment

import pyugrid
import pysgrid
import zipfile
from gnome.utilities.file_tools.data_helpers import _get_dataset


class PyGridSchema(base_schema.ObjType):
#     filename = SequenceSchema(SchemaNode(String()), accept_scalar=True)
    filename = SchemaNode(typ=Sequence(accept_scalar=True), children=[SchemaNode(String())])


class PyGrid(Serializable):

    _def_count = 0

    _state = copy.deepcopy(Serializable._state)
    _schema = PyGridSchema
    _state.add_field([Field('filename', save=True, update=True, isdatafile=True)])

    def __new__(cls, *args, **kwargs):
        '''
        If you construct a PyGrid object directly, you will always
        get one of the child types based on your input
        '''
        if cls is not PyGrid_U and cls is not PyGrid_S:
            if 'faces' in kwargs:
                cls = PyGrid_U
            else:
                cls = PyGrid_S
#         cls.obj_type = c.obj_type
        return super(type(cls), cls).__new__(cls, *args, **kwargs)

    def __init__(self,
                 filename=None,
                 *args,
                 **kwargs):
        '''
        Init common to all PyGrid types. This constructor will take all the kwargs of both
        pyugrid.UGrid and pysgrid.SGrid. See their documentation for details

        :param filename: Name of the file this grid was constructed from, if available.
        '''
        super(PyGrid, self).__init__(**kwargs)
        if 'name' in kwargs:
            self.name = kwargs['name']
        else:
            self.name = self.name + '_' + str(type(self)._def_count)
        self.obj_type = str(type(self).__bases__[0])
        self.filename = filename
        type(self)._def_count += 1

    @classmethod
    def load_grid(cls, filename, topology_var):
        '''
        Redirect to grid-specific loading routine.
        '''
        if hasattr(topology_var, 'face_node_connectivity'):
            cls = PyGrid_U
            return cls.from_ncfile(filename)
        else:
            cls = PyGrid_S
            return cls.load_grid(filename)
        pass

    @classmethod
    def from_netCDF(cls, filename, dataset=None, grid_type=None, grid_topology=None, *args, **kwargs):
        '''
        :param filename: File containing a grid
        :param dataset: Takes precedence over filename, if provided.
        :param grid_type: Must be provided if Dataset does not have a 'grid_type' attribute, or valid topology variable
        :param grid_topology: A dictionary mapping of grid attribute to variable name. Takes precendence over discovered attributes
        :param **kwargs: All kwargs to SGrid or UGrid are valid, and take precedence over all.
        :returns: Instance of PyGrid_U, PyGrid_S, or PyGrid_R
        '''
        gf = dataset = _get_dataset(filename, dataset)
        gt = PyGrid._find_topology(filename)
        if gt is None:
            if grid_type is None and not hasattr(gf, 'grid_type'):
                raise ValueError('Unable to determine grid type. Dataset must have a "grid_type" \
                                 attribute, a valid topology variable, or the parameter \
                                 "grid_type" must be provided')
            spec_args = {}
            if grid_topology is not None:
                for k, v in grid_topology.items():
                    spec_args[k] = gf[v][:]
            cls = PyGrid._get_grid_type(gf, grid_type)
            found_args = cls._find_required_grid_attrs(filename, gf)[0]
            found_args.update(spec_args)
            found_args.update(kwargs)
            return cls(filename, *args, **found_args)
        else:
            # If a netCDF topology variable is found, then use it
            rv = cls.load_grid(filename, gt)
            rv.filename = filename
#             rv.__init__(filename, *args, **kwargs)
            return rv

    @classmethod
    def _find_required_grid_attrs(cls, filename, dataset=None):
        gf_vars = dataset.variables if dataset is not None else _get_dataset(filename).variables
        init_args = {}
        '''
        This function is the top level 'search for attributes' function. If there are any
        common attributes to all potential grid types, they will be sought here.
        '''
        node_attrs = ['node_lon', 'node_lat']
        node_coord_names = [['node_lon', 'node_lat'], ['lon', 'lat'], ['lon_psi', 'lat_psi']]
        composite_node_names = ['nodes', 'node']

        for n1, n2 in node_coord_names:
            if n1 in gf_vars and n2 in gf_vars:
                init_args[node_attrs[0]] = gf_vars[n1][:]
                init_args[node_attrs[1]] = gf_vars[n2][:]
                break
        if node_attrs[0] not in init_args:
            for n in composite_node_names:
                if n in gf_vars:
                    v = gf_vars[n][:].reshape(-1, 2)
                    init_args[node_attrs[0]] = v[:, 0]
                    init_args[node_attrs[0]] = v[:.1]
                    break
        if node_attrs[0] not in init_args:
            raise ValueError('Unable to find node coordinates.')
        return init_args, gf_vars

    @classmethod
    def new_from_dict(cls, dict_):
        dict_.pop('json_')
        filename = dict_['filename']
        rv = cls.from_netCDF(filename)
        rv.__class__._restore_attr_from_save(rv, dict_)
        print dict_
        rv._id = dict_.pop('id') if 'id' in dict_ else rv.id
        rv.__class__._def_count -= 1
        return rv

    @staticmethod
    def _get_grid_type(dataset, grid_type=None):
        grid_type = grid_type if grid_type is not None else dataset.grid_type
        if grid_type is not None:
            if grid_type.lower() in ['sgrid', 'pygrid_s', 'staggered', 'curvilinear', 'roms']:
                return PyGrid_S
            if grid_type.lower() in ['ugrid', 'pygrid_u', 'triangular', 'unstructured']:
                return PyGrid_U
        else:
            raise ValueError("Unable to determine grid type")

    @staticmethod
    def _find_topology(filename,
                       dataset=None):
        gf = dataset
        if gf is None:
            gf = _get_dataset(filename)
        gts = []
        for v in gf.variables:
            if hasattr(v, 'cf_role') and 'topology' in v.cf_role:
                gts.append(v)
#         gts = gf.get_variables_by_attributes(cf_role=lambda t: t is not None and 'topology' in t)
        if len(gts) != 0:
            return gts[0]
        else:
            return None

    @property
    def shape(self):
        return self.node_lon.shape

    def __eq__(self, o):
        if self is o:
            return True
        for n in ('nodes', 'faces'):
            if hasattr(self, n) and hasattr(o, n) and getattr(self, n) is not None and getattr(o, n) is not None:
                s = getattr(self, n)
                s2 = getattr(o, n)
                if s.shape != s2.shape or np.any(s != s2):
                    return False
        return True

    def serialize(self, json_='webapi'):
        pass
        return Serializable.serialize(self, json_=json_)

    def _write_grid_to_file(self, pth):
        self.save_as_netcdf(pth)

    def save(self, saveloc, references=None, name=None):
        '''
        INCOMPLETE
        Write Wind timeseries to file or to zip,
        then call save method using super
        '''
#         name = self.name
#         saveloc = os.path.splitext(name)[0] + '_grid.GRD'

        if zipfile.is_zipfile(saveloc):
            if self.filename is None:
                self._write_grid_to_file(saveloc)
                self._write_grid_to_zip(saveloc, saveloc)
                self.filename = saveloc
#             else:
#                 self._write_grid_to_zip(saveloc, self.filename)
        else:
            if self.filename is None:
                self._write_grid_to_file(saveloc)
                self.filename = saveloc
        return super(PyGrid, self).save(saveloc, references, name)


class PyGrid_U(PyGrid, pyugrid.UGrid):

    @classmethod
    def _find_required_grid_attrs(cls, filename, dataset=None):

        # Get superset attributes
        init_args, gf_vars = super(PyGrid_U, cls)._find_required_grid_attrs(filename=filename, dataset=dataset)

        face_attrs = ['faces']
        face_var_names = ['nv', 'ele']

        for n in face_var_names:
            if n in gf_vars:
                init_args[face_attrs[0]] = gf_vars[n][:]
                break
        if face_attrs[0] in init_args:
            if init_args[face_attrs[0]].shape[0] == 3:
                init_args[face_attrs[0]] = np.ascontiguousarray(np.array(init_args[face_attrs[0]]).T - 1)
            return init_args, gf_vars
        else:
            raise ValueError('Unable to find faces variable')


class PyGrid_S(PyGrid, pysgrid.SGrid):

    @classmethod
    def _find_required_grid_attrs(cls, filename, dataset=None):

        # THESE ARE ACTUALLY ALL OPTIONAL. This should be migrated when optional attributes are dealt with
        # Get superset attributes
        init_args, gf_vars = super(PyGrid_S, cls)._find_required_grid_attrs(filename, dataset=dataset)

        center_attrs = ['center_lon', 'center_lat']
        center_coord_names = [['center_lon', 'center_lat'], ['lon_rho', 'lat_rho']]

        edge1_attrs = ['edge1_lon', 'edge1_lat']
        edge1_coord_names = [['edge1_lon', 'edge1_lat'], ['lon_u', 'lat_u']]

        edge2_attrs = ['edge2_lon', 'edge2_lat']
        edge2_coord_names = [['edge2_lon', 'edge2_lat'], ['lon_v', 'lat_v']]

        for attr, names in (zip((center_attrs, edge1_attrs, edge2_attrs),
                                (center_coord_names, edge1_coord_names, edge2_coord_names))):
            for n1, n2 in names:
                if n1 in gf_vars and n2 in gf_vars:
                    init_args[attr[0]] = gf_vars[n1][:]
                    init_args[attr[1]] = gf_vars[n2][:]
                    break
        return init_args, gf_vars


class GridSchema(base_schema.ObjType):
    name = 'grid'
    grid_type = SchemaNode(Float(), missing=drop)


class Grid(Environment, Serializable):
    '''
    Defines a grid for a current or wind
    '''

    _update = []

    # used to create new obj or as readonly parameter
    _create = []
    _create.extend(_update)

    _state = copy.deepcopy(Environment._state)
    _state.add(save=_create, update=_update)
    _schema = GridSchema

    def __init__(self, filename, topology_file=None, grid_type=1,
                 extrapolate=False, time_offset=0,
                 **kwargs):
        """
        Initializes a grid object from a file and a grid type

        maybe allow a grid to be passed in eventually, otherwise filename required

        All other keywords are optional. Optional parameters (kwargs):

        :param grid_type: default is 1 - regular grid (eventually figure this out from file)

        """
        self._grid_type = grid_type

        self.filename = filename
        self.topology_file = topology_file

        if self._grid_type == 1:
            self.grid = CyTimeGridWindRect(filename)
        elif self._grid_type == 2:
            self.grid = CyTimeGridWindCurv(filename, topology_file)
        else:
            raise Exception('grid_type not implemented ')

        self.grid.load_data(filename, topology_file)

        super(Grid, self).__init__(**kwargs)

    def __repr__(self):
        self_ts = None
        return ('{0.__class__.__module__}.{0.__class__.__name__}('
                'timeseries={1}'
                ')').format(self, self_ts)

    def __str__(self):
        return ("Grid ( "
                "grid_type='curvilinear')")

    @property
    def grid_type(self):
        return self._grid_type

    @grid_type.setter
    def grid_type(self, value):
        """
        probably will figure out from the file
        """
        # may want a check on value
        self._grid_type = value

    extrapolate = property(lambda self: self.grid.extrapolate,
                           lambda self, val: setattr(self.grid,
                                                     'extrapolate',
                                                     val))

    time_offset = property(lambda self: self.grid.time_offset / 3600.,
                           lambda self, val: setattr(self.grid,
                                                     'time_offset',
                                                     val * 3600.))

    def prepare_for_model_run(self, model_time):
        """
        Not sure we need to do anything here
        """

        pass

    def prepare_for_model_step(self, model_time):
        """
        Make sure we have the right data loaded
        """
        model_time = date_to_sec(model_time)
        self.grid.set_interval(model_time)

    def get_value(self, time, location):
        '''
        Return the value at specified time and location.
        '''
        data = self.grid.get_value(time, location)

        return data

    def get_values(self, model_time, positions, velocities):
        '''
        Return the values for the given positions

        '''
        data = self.grid.get_values(model_time, positions, velocities)

        return data

    def serialize(self, json_='webapi'):

        toserial = self.to_serialize(json_)
        schema = self.__class__._schema()

        serial = schema.serialize(toserial)

        return serial

    @classmethod
    def deserialize(cls, json_):

        schema = cls._schema()

        _to_dict = schema.deserialize(json_)

        return _to_dict


