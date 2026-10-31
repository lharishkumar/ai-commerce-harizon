FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm install
FROM node:20-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:1234
ARG NEXT_PUBLIC_LIVEKIT_MODE=browser
ARG NEXT_PUBLIC_LIVEKIT_URL=ws://localhost:7880
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_LIVEKIT_MODE=$NEXT_PUBLIC_LIVEKIT_MODE NEXT_PUBLIC_LIVEKIT_URL=$NEXT_PUBLIC_LIVEKIT_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
