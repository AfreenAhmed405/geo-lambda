# Lambda Geospatial Processing API

This AWS Lambda function processes geospatial data files (Shapefiles, GeoTIFFs, and PNG previews) for a given area defined by a GeoJSON clip. It performs clipping, masking, and generates both raster and vector outputs, which are automatically uploaded to S3 and publishes results to SNS.

---

## Features

- Accepts geospatial jobs with:
  - **GeoJSON** defining the clipping area
  - **Shapefile** ZIP
  - **Raster GeoTIFF**
- Clips shapefiles to the given GeoJSON
- Creates a Super Resolution raster (`.tif`) and a PNG preview
- Converts black pixels in PNG to transparent
- Uploads outputs to **S3** and returns public URLs
- Computes transformed geographical bounds (EPSG:4326)
- Returns a final GeoJSON of the clipped shapefile