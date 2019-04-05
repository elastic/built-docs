#!/bin/bash
cd /opt/node_apps/built-docs && cp redirects.conf /opt/nginx-naxsi/conf/guide_redirects.conf && service nginx configtest && service nginx reload
