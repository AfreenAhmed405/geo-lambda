# core.py

import os
import json
import boto3
import zipfile
import rasterio
import geopandas as gpd
from rasterio.mask import mask
from PIL import Image
from shapely.geometry import MultiPoint
from pyproj import Transformer
import numpy as np

Image.MAX_IMAGE_PIXELS = None

def upload_to_s3(file_path, s3_filename, bucket="ml-inference-output"):
    s3 = boto3.client("s3")
    s3.upload_file(file_path, bucket, f"uploads/{s3_filename}")
    return f"https://{bucket}.s3.amazonaws.com/uploads/{s3_filename}"

def mask_black_with_transparent(output_path):
    img = Image.open(output_path).convert("RGBA")
    new_data = [
        (0, 0, 0, 0) if item[:3] == (0, 0, 0) else item
        for item in img.getdata()
    ]
    img.putdata(new_data)
    img.save(output_path, "PNG")

def get_transformed_geo_bounds(tif_path, target_epsg=4326):
    with rasterio.open(tif_path) as src:
        bounds = src.bounds
        transformer = Transformer.from_crs(src.crs, f"epsg:{target_epsg}", always_xy=True)
        nw = transformer.transform(bounds.left, bounds.top)
        se = transformer.transform(bounds.right, bounds.bottom)
        return {
            "north": max(nw[1], se[1]),
            "south": min(nw[1], se[1]),
            "east": max(nw[0], se[0]),
            "west": min(nw[0], se[0]),
        }

def process_geospatial_job(job_input):
    print("==> Processing geospatial job")

    req_id = job_input["request_id"]
    tmp_dir = f"/tmp/job_{req_id}"
    os.makedirs(tmp_dir, exist_ok=True)

    # Save GeoJSON
    geojson_path = os.path.join(tmp_dir, f"{req_id}.geojson")
    geojson_data = job_input["geojson"]

    # Parse string to dict if needed
    if isinstance(geojson_data, str):
        geojson_data = json.loads(geojson_data)

    with open(geojson_path, "w") as f:
        json.dump(job_input["geojson"], f)

    # Download shapefile ZIP and raster TIF from S3
    s3 = boto3.client("s3")
    shapefile_zip_path = os.path.join(tmp_dir, f"{req_id}_shapefile.zip")
    s3.download_file("ml-inference-output", job_input["shapefile_s3"], shapefile_zip_path)
    raster_path = os.path.join(tmp_dir, f"{req_id}.tif")
    s3.download_file("ml-inference-output", job_input["raster_s3"], raster_path)

    print("==> Downloaded required files from S3")

    # Unzip shapefile
    with zipfile.ZipFile(shapefile_zip_path, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)

    print("==> Total Shapefile unzipped")

    # Find .shp file
    shp_path = None
    for root, _, files in os.walk(tmp_dir):
        for file in files:
            if file.endswith(".shp"):
                shp_path = os.path.join(root, file)
                break
        if shp_path:
            break

    if not shp_path:
        raise FileNotFoundError("No .shp file found in extracted ZIP")
    shp_full_path = os.path.join(tmp_dir, shp_path)

    # Read files
    clip_gdf = gpd.read_file(geojson_path)
    shapefile_gdf = gpd.read_file(shp_full_path)
    clip_gdf = clip_gdf.to_crs(shapefile_gdf.crs)
    clipped = gpd.clip(shapefile_gdf, clip_gdf)
    clipped['geometry'] = clipped['geometry'].apply(
        lambda geom: MultiPoint([geom]) if geom.geom_type == 'Point' else geom
    )

    # Save GeoJSON
    clipped = clipped.to_crs(epsg=4326)
    geojson_filename = f"{req_id}_pci.geojson"
    geojson_out = os.path.join(tmp_dir, geojson_filename)
    clipped.to_file(geojson_out, driver="GeoJSON")

    print("==> Created geojson")

    # Zip file
    shapefile_base = os.path.join(tmp_dir, f"clipped_{req_id}")  # no extension
    clipped.to_file(shapefile_base + ".shp", driver="ESRI Shapefile")
    zip_filename = f"pci_shape_file_{req_id}.zip"
    zip_path = os.path.join(tmp_dir, zip_filename)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for ext in ["shp", "shx", "dbf", "prj", "cpg"]:
            path = f"{shapefile_base}.{ext}"
            if os.path.exists(path):
                zipf.write(path, arcname=os.path.basename(path))
            else:
                print(f"Missing: {path}")
    
    print("==> Created Shapefile zip")

    # Clean up .shp components
    for ext in ["shp", "shx", "dbf", "prj", "cpg"]:
        path = f"{shapefile_base}.{ext}"
        if os.path.exists(path):
            os.remove(path)

    # Raster mask
    with rasterio.open(raster_path) as src:
        clip_gdf = clip_gdf.to_crs(src.crs)
        geometry = [json.loads(clip_gdf.to_json())['features'][0]['geometry']]
        out_image, out_transform = mask(src, geometry, crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

        tif_out_path = os.path.join(tmp_dir, f"sri_{req_id}.tif")
        with rasterio.open(tif_out_path, "w", **out_meta) as dest:
            dest.write(out_image)
    
    print("==> Created Super Resolution Image")

    # PNG preview
    arr = out_image[0]
    arr_min, arr_max = arr.min(), arr.max()
    if arr_max > arr_min:
        arr_norm = ((arr - arr_min) / (arr_max - arr_min) * 255).astype('uint8')
    else:
        arr_norm = np.zeros_like(arr, dtype='uint8')

    img = Image.fromarray(arr_norm, mode='L')
    png_out_path = os.path.join(tmp_dir, f"sri_{req_id}.png")
    img.save(png_out_path)
    mask_black_with_transparent(png_out_path)

    print("==> Created PNG preview")

    # Upload files
    urls = {
        "geojson_s3": upload_to_s3(geojson_out, geojson_filename),
        "tif_s3": upload_to_s3(tif_out_path, os.path.basename(tif_out_path)),
        "png_s3": upload_to_s3(png_out_path, os.path.basename(png_out_path)),
        "zip_s3": upload_to_s3(zip_path, os.path.basename(zip_path)),
        "bounds": get_transformed_geo_bounds(tif_out_path),
        "geojson_result": clipped.to_json()
    }

    print("==> Uploaded files to S3")

    try:
        import shutil
        shutil.rmtree(tmp_dir)
        print(f"==> Cleaned up temporary directory: {tmp_dir}")
    except Exception as e:
        print(f"[WARNING] Failed to clean up {tmp_dir}: {e}")

    return urls