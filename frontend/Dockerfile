FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# CRA bakes these in at build time
ARG REACT_APP_API_URL=http://localhost:8000
ARG REACT_APP_OIDC_ISSUER=http://localhost:8081
ARG REACT_APP_OIDC_CLIENT_ID=patient-intake-frontend
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
