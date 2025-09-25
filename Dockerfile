# Base image for Python 3.11 + Lambda runtime
FROM public.ecr.aws/lambda/python:3.11

# System dependencies for geospatial libraries
RUN yum install -y \
    gcc \
    proj-devel \
    geos-devel \
    sqlite-devel \
    libcurl-devel \
    libxml2-devel \
    libpng-devel \
    libjpeg-devel \
    zlib-devel \
    gdal-devel \
    && yum clean all

# Set working directory
WORKDIR /var/task

# Copy project files
COPY . .

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --only-binary :all: -r requirements.txt

# Set Lambda entrypoint
CMD ["lambda_handler.lambda_handler"]