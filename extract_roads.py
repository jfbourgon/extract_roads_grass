import os
import gc
import csv
import sys
import time
import shutil
import tempfile
import argparse
import binascii
import subprocess
from pathlib import Path
from osgeo import gdal, osr


gdal.DontUseExceptions()
#grass8bin = grass8bin_win = r"C:\OSGeo4W\bin\grass84.bat"

def cmd_interface(argv=None):
    
    parser = argparse.ArgumentParser(
        usage="%(prog)s [-h HELP] use -h to get supported arguments.",
        description="Extract roads from raster masks.",
    )
    parser.add_argument("-i", "--input_csv", nargs=1, help="A csv of all road raster masks")
    parser.add_argument("-wd", "--work_dir", nargs=1, help="The dir for saving geopackages")
    
    args = parser.parse_args()
    input_csv = args.input_csv[0]
    work_dir = args.work_dir[0] 

    arguments = {
        "input_csv": input_csv,
        "work_dir": work_dir,
    }
    return arguments

def config_grass():
    
    
    result = subprocess.run(['where', 'grass84.bat'], capture_output=True, text=True, check=True)
        
    # Output will contain the path to grass84.bat
    grass8bin = grass8bin_win = result.stdout.strip()
    
    if grass8bin:
        print(f"Path to grass84 bat: {grass8bin}")
    else:
        print("grass84.bat not found.")

    """ The following command is for checking if grass has its start script"""
    startcmd = grass8bin + ' --config path'
    p = subprocess.Popen(startcmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        print(f'ERROR: {err.decode()}', file=sys.stderr)
        print(f'ERROR: Cannot find GRASS GIS 7 start script ({startcmd})', file=sys.stderr)
        sys.exit(-1)

    """ Now setting GISBASE"""
    if b"OSGEO4W home is" in out:
        gisbase = out.strip().decode().split('\n')[1]
    else:
        gisbase = out.strip().decode()

    os.environ['GRASS_SH'] = os.path.join(gisbase, 'msys', 'bin', 'sh.exe')
    os.environ['GISBASE'] = gisbase

    """ Now setting GRASS Python path"""
    gpydir = os.path.join(gisbase, "etc", "python")
    sys.path.append(os.environ.get('PYTHONPATH', ''))
    sys.path.append(gpydir)
    
    return grass8bin

    
if __name__ == "__main__":

    

    arguments = cmd_interface()
    grass8bin = grass8bin_win = config_grass()
    """ define GRASS DATABASE """
    gisdb = os.path.join(os.getenv('APPDATA', 'grassdata'))
    gisdb = os.path.join(tempfile.gettempdir(), 'grassdata')
    try:
        os.stat(gisdb)
    except:
        os.mkdir(gisdb)

    with open(arguments["input_csv"], newline='',encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        for road_mask in reader:
            # Creating the geofile path for storing the results
            road_dataset_name = os.path.splitext(os.path.basename(Path(road_mask[0])))[0]
            road_geopackage = Path(arguments["work_dir"]) / f"{road_dataset_name}.gpkg"
            # Getting the crs code of the layer
            road_dataset = gdal.Open(road_mask[0])
            location_epsg=""
            if road_dataset is not None:
                # Get the CRS from the dataset
                spatial_ref = osr.SpatialReference()
                spatial_ref.ImportFromWkt(road_dataset.GetProjectionRef())
                location_epsg = spatial_ref.GetAttrValue("AUTHORITY", 1)
                del spatial_ref
            del road_dataset
            if len(location_epsg) != 0:

                start_time = time.time()
                """ location/mapset: use random names """
                location = binascii.hexlify(os.urandom(8))
                mapset='PERMANENT'
                if isinstance(gisdb, bytes):
                    gisdb = gisdb.decode('utf-8')
                if isinstance(location, bytes):
                    location = location.decode('utf-8')

                # Create new location from EPSG code
                location_path = os.path.join(gisdb, location)
                startcmd = grass8bin + ' -c epsg:' + location_epsg + ' -e ' + location_path
                p = subprocess.Popen(startcmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = p.communicate()

                if p.returncode != 0:
                    print(f'ERROR: {err.decode()}', file=sys.stderr)
                    print(f'ERROR: Cannot generate location ({startcmd})', file=sys.stderr)
                    sys.exit(-1)
                else:
                    print(f'Created location {location_path}')
                
                ########
                """ Now the location with PERMANENT mapset exists."""
                os.environ['GISDBASE'] = gisdb
                os.environ['LANG'] = 'en_US'
                os.environ['LOCALE'] = 'C'


                # Import GRASS Python bindings
                import grass.script as grass
                import grass.script.setup as gsetup

                gsetup.init(gisdb,location, mapset)
                print(grass.read_command('g.gisenv', flags='s'))
                # Print current GRASS GIS environment
                grass.message('--- GRASS GIS 7: Current GRASS GIS 7 environment:')
                print(grass.gisenv())
                output_name = "roads"
                #sys.path.append(subprocess.check_output([grass8bin, "--config", "python_path"], text=True, shell=True).strip())
                
                grass.run_command('r.import', input=road_mask, output=output_name, overwrite=True)
                grass.run_command('g.region', flags='p', raster=output_name)
                grass.run_command('r.to.vect', input=output_name, output='roads_v', type='line', flags='s')
                grass.run_command('v.generalize', input='roads_v', output='roads_v_smooth', method='chaiken', threshold=10)
                grass.run_command('v.out.ogr', 
                            input='roads_v_smooth', 
                            output=str(road_geopackage), 
                            format='GPKG', 
                            layer='roads_1', 
                            flags='c', 
                            overwrite=True)
                
                total_time = time.time() - start_time
                print(
                    f"--------------------------- Road Extraction for {road_dataset_name} Completed in {:.0f}m {:.0f}s -------------------------------".format(
                        total_time // 60, total_time % 60
                    )
                )
                shutil.rmtree(location_path)
                gc.collect()

