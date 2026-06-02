# Stage 1: Build React app
FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=http://192.168.1.10:8005
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


# Stage 2: Production static server
FROM node:22-alpine AS production

WORKDIR /app

RUN npm install -g serve

COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]