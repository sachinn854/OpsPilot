FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

RUN printf 'server {\n\
    listen __PORT__;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

CMD ["/bin/sh", "-c", "sed -i \"s/__PORT__/${PORT:-80}/g\" /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
