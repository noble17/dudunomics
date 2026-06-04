# Build stage
FROM node:20-slim AS builder
WORKDIR /app

# Install pnpm (if you use it, otherwise use npm)
RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

COPY . .

# Set environment variable for build
ARG API_URL
ENV API_URL=$API_URL

RUN pnpm build

# Production stage
FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3333
ENV PORT 3333
# set hostname to localhost
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
