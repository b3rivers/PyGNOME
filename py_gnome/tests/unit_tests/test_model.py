#!/usr/bin/env python

"""
test code for the model class

not a lot to test by itself, but a start

"""
import pytest
import os, shutil
from datetime import datetime, timedelta
import numpy as np
import gnome.model
import gnome.map
from gnome import movers, weather
import gnome.spill

def test_init():
    model = gnome.model.Model()
    
def test_start_time():
    model = gnome.model.Model()

    st = datetime.now()
    model.start_time = st
    assert model.start_time == st
    
    model.step()
    
    st = datetime(2012, 8, 12, 13)
    model.start_time = st
    
    assert model.current_time_step == -1
    assert model.start_time == st

def test_timestep():
    model = gnome.model.Model()

    ts = timedelta(hours=1)
    model.time_step = ts
    assert model.time_step == ts.total_seconds()
    
    dur = timedelta(days=3)
    model.duration = dur
    assert model._duration == dur

def test_simple_run():
    """
    pretty much all this tests is that the model will run
    """
    
    start_time = datetime(2012, 9, 15, 12, 0)
    
    model = gnome.model.Model()
    
    model.map = gnome.map.GnomeMap()
    a_mover = movers.simple_mover.SimpleMover(velocity=(1.0, 2.0, 0.0))
    
    model.movers += a_mover
    assert len(model.movers) == 1

    spill = gnome.spill.PointReleaseSpill(num_LEs=10,
                                          start_position = (0.0, 0.0, 0.0),
                                          release_time = start_time,
                                          )
    
    model.spills += spill
    assert len(model.spills) == 1
    model.start_time = spill.release_time
    
    # test iterator:
    for step in model:
        print "just ran time step: %s"%model.current_time_step

    # reset and run again:
    model.reset()
    # test iterator:
    for step in model:
        print "just ran time step: %s"%model.current_time_step
        
    assert True
    
def test_simple_run_with_map():
    """
    pretty much all this tests is that the model will run
    """
    
    start_time = datetime(2012, 9, 15, 12, 0)
    
    model = gnome.model.Model()
    
    model.map = gnome.map.MapFromBNA( 'SampleData/MapBounds_Island.bna',
                                refloat_halflife=6*3600, #seconds
                                )
    a_mover = movers.simple_mover.SimpleMover(velocity=(1.0, 2.0, 0.0))
    
    model.movers += a_mover
    assert len(model.movers) == 1

    spill = gnome.spill.PointReleaseSpill(num_LEs=10,
                                          start_position = (0.0, 0.0, 0.0),
                                          release_time = start_time,
                                          )
    
    model.spills += spill
    assert len(model.spills) == 1
    model.start_time = spill.release_time
    
    # test iterator:
    for step in model:
        print "just ran time step: %s"%step

    # reset and run again:
    model.reset()
    # test iterator:
    for step in model:
        print "just ran time step: %s"%step
        
    assert True

import gnome.utilities.map_canvas
from gnome.utilities.file_tools import haz_files
def test_simple_run_with_image_output():
    """
    pretty much all this tests is that the model will run and output images
    """
    
    # create a place for test images (cleaning out any old ones)
    images_dir = "Test_images"
    if os.path.isdir(images_dir):
        shutil.rmtree(images_dir)
    os.mkdir(images_dir)

    start_time = datetime(2012, 9, 15, 12, 0)
    
    model = gnome.model.Model()
    model.duration = timedelta(hours=1)

    mapfile = "SampleData/MapBounds_Island.bna"

    # the land-water map
    model.map = gnome.map.MapFromBNA( mapfile,
                                      refloat_halflife=6*3600, #seconds
                                     )
    # the image output map
    map = gnome.utilities.map_canvas.MapCanvas((400, 300))
    polygons = haz_files.ReadBNA(mapfile, "PolygonSet")
    map.set_land(polygons)
    model.output_map = map
    
    a_mover = movers.simple_mover.SimpleMover(velocity=(1.0, -1.0, 0.0))
    model.movers += a_mover
    assert len(model.movers) == 1

    N = 10 # a line of ten points
    start_points = np.zeros((N, 3) , dtype=np.float64)
    start_points[:,0] = np.linspace(-127.1, -126.5, N)
    start_points[:,1] = np.linspace( 47.93, 48.1, N)
    #print start_points
    spill = gnome.spill.PointReleaseSpill(num_LEs=10,
                                          start_position = start_points,
                                          release_time = start_time,
                                          )
    
    model.spills += spill
    assert len(model.spills) == 1
    model.start_time = spill.release_time
    #image_info = model.next_image()

    num_steps_output = 0
    while True:
         print "calling next_image"
         try:
             image_info = model.next_image(images_dir)
             num_steps_output += 1
             print image_info
         except StopIteration:
             print "Done with the model run"
             break

    assert num_steps_output == (model.duration.total_seconds() / model.time_step) + 1 # there is the zeroth step, too.


def test_mover_api():
    """
    Test the API methods for adding and removing movers to the model.
    """
    start_time = datetime(2012, 1, 1, 0, 0)

    model = gnome.model.Model()
    model.duration = timedelta(hours=12)
    model.time_step = timedelta(hours = 1)
    model.start_time = start_time

    mover_1 = movers.simple_mover.SimpleMover(velocity=(1.0, -1.0, 0.0))
    mover_2 = movers.simple_mover.SimpleMover(velocity=(1.0, -1.0, 0.0))
    mover_3 = movers.simple_mover.SimpleMover(velocity=(1.0, -1.0, 0.0))
    mover_4 = movers.simple_mover.SimpleMover(velocity=(1.0, -1.0, 0.0))

    # test our add object methods
    model.movers += mover_1
    model.movers += mover_2

    # test our get object methods
    assert(model.movers[mover_1.id] == mover_1)
    assert(model.movers[mover_2.id] == mover_2)
    with pytest.raises(KeyError):
        l__temp = model.movers['Invalid']

    # test our iter and len object methods
    assert len(model.movers) == 2
    assert len([m for m in model.movers]) == 2
    for m1, m2 in zip(model.movers, [mover_1, mover_2]):
        assert m1 == m2

    # test our add objectlist methods
    model.movers += [mover_3, mover_4]
    assert [m for m in model.movers] == [mover_1, mover_2, mover_3, mover_4]

    # test our remove object methods
    del model.movers[mover_3.id]
    assert [m for m in model.movers] == [mover_1, mover_2, mover_4]
    with pytest.raises(KeyError):
        # our key should also be gone after the delete
        l__temp = model.movers[mover_3.id]

    # test our replace method
    model.movers[mover_2.id] = mover_3
    assert [m for m in model.movers] == [mover_1, mover_3, mover_4]
    assert model.movers[mover_3.id] == mover_3
    with pytest.raises(KeyError):
        # our key should also be gone after the delete
        l__temp = model.movers[mover_2.id]


def test_all_movers():
    """
    a test that tests that all the movers at least can be run

    add new ones as they come along!
    """

    start_time = datetime(2012, 1, 1, 0, 0)
    
    model = gnome.model.Model()
    model.duration = timedelta(hours=12)
    model.time_step = timedelta(hours = 1)
    model.start_time = start_time

    # a spill
    model.spills += gnome.spill.PointReleaseSpill(num_LEs=10,
                                                  start_position = (0.0, 0.0, 0.0),
                                                  release_time = start_time,
                                                  )
    assert len(model.spills) == 1

    # the land-water map
    model.map = gnome.map.GnomeMap() # the simpleset of maps
    
    # simplemover
    model.movers += movers.simple_mover.SimpleMover(velocity=(1.0, -1.0, 0.0))
    assert len(model.movers) == 1

    # random mover
    model.movers += gnome.movers.RandomMover(diffusion_coef=100000)
    assert len(model.movers) == 2

    # wind mover
    series = np.array( (start_time, ( 10,   45) ),  dtype=gnome.basic_types.datetime_value_2d).reshape((1,))
    model.movers += gnome.movers.WindMover(weather.Wind(timeseries=series, units='meter per second'))
    assert len(model.movers) == 3
  
    
    # run the model all the way...
    num_steps_output = 0
    for step in model:
        num_steps_output += 1
        print "running step:", step

    assert num_steps_output == (model.duration.total_seconds() / model.time_step) + 1 # there is the zeroth step, too.
    
if __name__ == "__main__":
    test_all_movers()
    
    
    

    