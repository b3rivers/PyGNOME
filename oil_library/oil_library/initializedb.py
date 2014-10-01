import os
import sys

import transaction
from sqlalchemy import engine_from_config

from slugify import slugify_filename

from .oil_library_parse import OilLibraryFile

from .models import (DBSession,
                     Base,
                     Oil,
                     Synonym,
                     Density,
                     KVis,
                     DVis,
                     Cut,
                     Toxicity)


def initialize_sql(settings):
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.create_all(engine)


def load_database(settings):
    with transaction.manager:
        # -- Our loading routine --
        session = DBSession()

        # 1. purge our builtin rows if any exist
        sys.stderr.write('Purging old records in database')
        num_purged = purge_old_records(session)
        print 'finished!!!  %d rows processed.' % (num_purged)

        # 2. we need to open our OilLib file
        print 'opening file: %s ...' % (settings['oillib.file'])
        fd = OilLibraryFile(settings['oillib.file'])
        print 'file version:', fd.__version__

        # 3. iterate over our rows
        sys.stderr.write('Adding new records to database')
        rowcount = 0
        for r in fd.readlines():
            if len(r) < 10:
                print 'got record:', r

            # 3a. for each row, we populate the Oil object
            add_oil_object(session, fd.file_columns, r)

            if rowcount % 100 == 0:
                sys.stderr.write('.')

            rowcount += 1

        print 'finished!!!  %d rows processed.' % (rowcount)


def purge_old_records(session):
    oilobjs = session.query(Oil).filter(Oil.custom == False)

    rowcount = 0
    for o in oilobjs:
        session.delete(o)

        if rowcount % 100 == 0:
            sys.stderr.write('.')

        rowcount += 1

    transaction.commit()
    return rowcount


def add_oil_object(session, file_columns, row_data):
    file_columns = [slugify_filename(c).lower()
                    for c in file_columns]
    row_dict = dict(zip(file_columns, row_data))

    fix_pour_point(row_dict)
    fix_flash_point(row_dict)
    fix_preferred_oils(row_dict)

    oil = Oil(**row_dict)

    add_synonyms(session, oil, row_dict)
    add_densities(oil, row_dict)
    add_kinematic_viscosities(oil, row_dict)
    add_dynamic_viscosities(oil, row_dict)
    add_distillation_cuts(oil, row_dict)
    add_toxicity_effective_concentrations(oil, row_dict)
    add_toxicity_lethal_concentrations(oil, row_dict)

    session.add(oil)
    transaction.commit()


def fix_pour_point(kwargs):
    # kind of weird behavior...
    # pour_point min-max values have the following configurations:
    #     ['<', value] which means "less than" the max value
    #                  We will make it ['', value]
    #                  since max is really a max
    #     ['>', value] which means "greater than" the max value
    #                  We will make it [value, '']
    #                  since max is really a min
    if kwargs.get('pour_point_min_k') == '<':
        kwargs['pour_point_min_k'] = None
    if kwargs.get('pour_point_min_k') == '>':
        kwargs['pour_point_min_k'] = kwargs['pour_point_max_k']
        kwargs['pour_point_max_k'] = None


def fix_flash_point(kwargs):
    # same kind of weird behavior as pour point...
    if kwargs.get('flash_point_min_k') == '<':
        kwargs['flash_point_min_k'] = None
    if kwargs.get('flash_point_min_k') == '>':
        kwargs['flash_point_min_k'] = kwargs['flash_point_max_k']
        kwargs['flash_point_max_k'] = None


def fix_preferred_oils(kwargs):
    kwargs['preferred_oils'] = (True if kwargs.get('preferred_oils') == 'X'
                                else False)


def add_synonyms(session, oil, row_dict):
    if row_dict.get('Synonyms'):
        for s in row_dict.get('Synonyms').split(','):
            s = s.strip()
            if len(s) > 0:
                synonyms = (session.query(Synonym)
                            .filter(Synonym.name == s).all())
                if len(synonyms) > 0:
                    # we link the existing synonym object
                    oil.synonyms.append(synonyms[0])
                else:
                    # we add a new synonym object
                    oil.synonyms.append(Synonym(s))


def add_densities(oil, row_dict):
    for i in range(1, 5):
        obj_args = ('kg_m_3', 'ref_temp_k', 'weathering')
        row_fields = ['density_{0}_{1}'.format(i, a) for a in obj_args]

        if any([row_dict.get(k) for k in row_fields]):
            densityargs = {}

            for col, arg in zip(row_fields, obj_args):
                densityargs[arg] = row_dict.get(col)

            fix_weathering(densityargs)
            oil.densities.append(Density(**densityargs))


def fix_weathering(kwargs):
    # The weathering field is defined as an evaporation percentage
    # so if there is no weathering, we default to 0.0%
    if kwargs.get('weathering') == None:
        kwargs['weathering'] = '0e0'


def add_kinematic_viscosities(oil, row_dict):
    for i in range(1, 7):
        obj_args = ('m_2_s', 'ref_temp_k', 'weathering')
        row_fields = ['kvis_{0}_{1}'.format(i, a) for a in obj_args]

        if any([row_dict.get(k) for k in row_fields]):
            kvisargs = {}

            for col, arg in zip(row_fields, obj_args):
                kvisargs[arg] = row_dict.get(col)

            fix_weathering(kvisargs)
            oil.kvis.append(KVis(**kvisargs))


def add_dynamic_viscosities(oil, row_dict):
    for i in range(1, 7):
        obj_args = ('kg_ms', 'ref_temp_k', 'weathering')
        row_fields = ['dvis_{0}_{1}'.format(i, a) for a in obj_args]

        if any([row_dict.get(k) for k in row_fields]):
            dvisargs = {}

            for col, arg in zip(row_fields, obj_args):
                dvisargs[arg] = row_dict.get(col)

            fix_weathering(dvisargs)
            oil.dvis.append(DVis(**dvisargs))


def add_distillation_cuts(oil, row_dict):
    for i in range(1, 16):
        obj_args = ('vapor_temp_k', 'liquid_temp_k', 'fraction')
        row_fields = ['cut_{0}_{1}'.format(i, a) for a in obj_args]

        if any([row_dict.get(k) for k in row_fields]):
            cutargs = {}

            for col, arg in zip(row_fields, obj_args):
                cutargs[arg] = row_dict.get(col)

            oil.cuts.append(Cut(**cutargs))


def add_toxicity_effective_concentrations(oil, row_dict):
    for i in range(1, 4):
        obj_args = ('species', '24h', '48h', '96h')
        row_fields = ['tox_ec_{0}_{1}'.format(i, a) for a in obj_args]

        if any([row_dict.get(k) for k in row_fields]):
            toxargs = {}
            toxargs['tox_type'] = 'EC'

            for col, arg in zip(row_fields, obj_args):
                if arg[0].isdigit():
                    # table column names cannot start with a digit
                    arg = 'after_{0}'.format(arg)
                toxargs[arg] = row_dict.get(col)

            oil.toxicities.append(Toxicity(**toxargs))


def add_toxicity_lethal_concentrations(oil, row_dict):
    for i in range(1, 4):
        obj_args = ('species', '24h', '48h', '96h')
        row_fields = ['tox_lc_{0}_{1}'.format(i, a) for a in obj_args]

        if any([row_dict.get(k) for k in row_fields]):
            toxargs = {}
            toxargs['tox_type'] = 'LC'

            for col, arg in zip(row_fields, obj_args):
                if arg[0].isdigit():
                    # table column names cannot start with a digit
                    arg = 'after_{0}'.format(arg)
                toxargs[arg] = row_dict.get(col)

            oil.toxicities.append(Toxicity(**toxargs))


def make_db(oillib_file=None, db_file=None):
    '''
    Entry point for console_script installed by setup
    '''
    pck_loc = os.path.split(__file__)[0]

    if not db_file:
        db_file = os.path.join(pck_loc, 'OilLib.db')

    if not oillib_file:
        oillib_file = os.path.join(pck_loc, 'OilLib')

    sqlalchemy_url = 'sqlite:///{0}'.format(db_file)
    settings = {'sqlalchemy.url': sqlalchemy_url,
                'oillib.file': oillib_file}
    try:
        initialize_sql(settings)
        load_database(settings)
    except:
        print "FAILED TO CREATED OIL LIBRARY DATABASE \n"
        raise