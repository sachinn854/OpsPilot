#!/bin/sh
set -e
cat > /etc/nginx/conf.d/default.conf << EOF
server {
    listen ${PORT:-80};
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
exec nginx -g "daemon off;"
