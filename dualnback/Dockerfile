# Sử dụng Python image
FROM python:3.12

# Set working directory
WORKDIR /app

# Copy toàn bộ code
COPY . /app

# Cài đặt phụ thuộc
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Mở cổng
EXPOSE 2346

# Chạy Daphne server
CMD ["daphne", "-b", "0.0.0.0", "-p", "2346", "dualnback.asgi:application"]
