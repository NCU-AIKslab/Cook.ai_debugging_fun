# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve the static files with a lightweight server
FROM node:20-alpine

WORKDIR /app

# Install serve globally
RUN npm install -g serve

# Copy the build output from the build stage
COPY --from=build /app/dist ./dist

# Expose the port the app runs on
EXPOSE 3001

# Serve the static files
CMD ["serve", "-s", "dist", "-l", "3001"]
