#!/bin/bash -ex

# Build core containers
(cd elasticsearch && docker build -t sgaroncse/elasticsearch:7.0.0 .)
(cd apm-server && docker build -t sgaroncse/apm-server:7.0.0 .)
(cd ../.. && docker build -f alv4/docker/metricbeat/Dockerfile -t sgaroncse/metricbeat:7.0.0 .)
(cd nginx-ssl && docker build -t sgaroncse/nginx-ssl:1.15.10-1 .)
(cd nginx-ssl-dev && docker build -t sgaroncse/nginx-ssl-dev:1.15.10-1 .)
(cd riak && docker build -t sgaroncse/riak-kv:2.1.4 .)

# Build default dev containers
(cd ../.. && docker build -f alv4/docker/al_dev/Dockerfile -t sgaroncse/assemblyline_dev:latest -t sgaroncse/assemblyline_dev:4.0.4 .)
(cd ../.. && docker build -f alv4/docker/al_dev_py2/Dockerfile -t sgaroncse/assemblyline_dev_py2:latest -t sgaroncse/assemblyline_dev_py2:4.0.4 .)

# Build services containers
(cd ../.. && docker build -f alv4/docker/v3_services/v3_service_base_dev/Dockerfile -t sgaroncse/v3_service_base_dev:latest -t sgaroncse/v3_service_base_dev:3.3.4 .)
(cd ../.. && docker build -f alv4/docker/v3_services/alsvc_characterize/Dockerfile -t sgaroncse/alsvc_characterize:latest -t sgaroncse/alsvc_characterize:3.3.4 .)
(cd ../.. && docker build -f alv4/docker/v3_services/alsvc_extract/Dockerfile -t sgaroncse/alsvc_extract:latest -t sgaroncse/alsvc_extract:3.3.4 .)
(cd ../.. && docker build -f alv4/docker/v3_services/alsvc_pdfid/Dockerfile -t sgaroncse/alsvc_pdfid:latest -t sgaroncse/alsvc_pdfid:3.3.4 .)

