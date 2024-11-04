import os
import gc
import time
import tempfile
import argparse
import uuid
#import rasterio
from pathlib import Path
from osgeo import gdal, osr

# Import GRASS Python bindings
from grass_session import Session
import grass.script as grass
import grass.script.setup as gsetup

#gdal.DontUseExceptions()
MAPSET="PERMANENT"

def cmd_interface(argv=None):
    
    parser = argparse.ArgumentParser(
        usage="%(prog)s [-h HELP] use -h to get supported arguments.",
        description="Extract roads from a raster mask.",
    )
    parser.add_argument("-i", "--input", help="The path to the input road raster masks")
    parser.add_argument("-o", "--output", help="The path to the output road vector file")
    
    args = parser.parse_args()
    arguments = {
        "input": args.input,
        "output": args.output,
    }
    return arguments
   
if __name__ == "__main__":
    arguments = cmd_interface()

    # Creating the geofile path for storing the results
    road_dataset_path = Path(arguments["input"])
    road_dataset_name = road_dataset_path.stem
    road_geopackage = Path(arguments["output"]) / f"{road_dataset_name}.gpkg"

    # Getting the crs code of the layer
    road_dataset = gdal.Open(road_dataset_path)
    
    epsg=""
    if road_dataset is not None:
        # Get the CRS from the dataset
        projection = road_dataset.GetProjection()

        # Parse the projection information to get the EPSG code
        srs = osr.SpatialReference(wkt=projection)
        srs.AutoIdentifyEPSG()
        epsg = srs.GetAuthorityCode(None)   

    if epsg:
        start_time = time.time()
        
        with tempfile.TemporaryDirectory() as gisdb:
            with Session(gisdb=gisdb, 
                         location=str(uuid.uuid4()), 
                         create_opts= f"EPSG:{epsg}"):                
                # Print current GRASS GIS environment
                print("--- GRASS GIS - Current GRASS GIS environment ---")
                print(f"GRASS Version {grass.version().version}")
                print(grass.gisenv())
                
                output_name = "roads"
                grass.run_command('r.import', input=road_dataset_path, output=output_name, overwrite=True)
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
                    f"------------- Road Extraction for {road_dataset_name} Completed in {(total_time // 60):.0f}m {(total_time % 60):.0f}s -------------"
                )
                #shutil.rmtree(location_path)
                gc.collect()

