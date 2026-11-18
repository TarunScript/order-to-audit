FROM node:20-alpine

WORKDIR /app

RUN npm create vite@latest . -- --template react-ts && npm install

COPY . .

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
