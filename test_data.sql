-- NDK Dashboard MySQL Test Data
-- Database: mydb

USE mydb;

-- Create tables
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    city VARCHAR(50),
    country VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INT DEFAULT 0,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Insert test customers
INSERT INTO customers (first_name, last_name, email, phone, city, country) VALUES
('John', 'Doe', 'john.doe@example.com', '+1-555-0101', 'New York', 'USA'),
('Jane', 'Smith', 'jane.smith@example.com', '+1-555-0102', 'Los Angeles', 'USA'),
('Bob', 'Johnson', 'bob.johnson@example.com', '+1-555-0103', 'Chicago', 'USA'),
('Alice', 'Williams', 'alice.williams@example.com', '+44-20-1234-5678', 'London', 'UK'),
('Charlie', 'Brown', 'charlie.brown@example.com', '+1-555-0104', 'San Francisco', 'USA'),
('Diana', 'Davis', 'diana.davis@example.com', '+33-1-23-45-67-89', 'Paris', 'France'),
('Eve', 'Martinez', 'eve.martinez@example.com', '+34-91-123-4567', 'Madrid', 'Spain'),
('Frank', 'Garcia', 'frank.garcia@example.com', '+1-555-0105', 'Miami', 'USA'),
('Grace', 'Lee', 'grace.lee@example.com', '+82-2-1234-5678', 'Seoul', 'South Korea'),
('Henry', 'Wilson', 'henry.wilson@example.com', '+61-2-1234-5678', 'Sydney', 'Australia');

-- Insert test products
INSERT INTO products (name, description, price, stock_quantity, category) VALUES
('Laptop Pro 15', 'High-performance laptop with 15-inch display', 1299.99, 50, 'Electronics'),
('Wireless Mouse', 'Ergonomic wireless mouse with USB receiver', 29.99, 200, 'Electronics'),
('Mechanical Keyboard', 'RGB mechanical keyboard with blue switches', 89.99, 75, 'Electronics'),
('USB-C Hub', '7-in-1 USB-C hub with HDMI and ethernet', 49.99, 150, 'Electronics'),
('Laptop Backpack', 'Water-resistant backpack for 17-inch laptops', 59.99, 100, 'Accessories'),
('Desk Lamp', 'LED desk lamp with adjustable brightness', 39.99, 80, 'Office'),
('Notebook Set', 'Set of 3 premium notebooks', 19.99, 300, 'Stationery'),
('Pen Set', 'Professional pen set with case', 24.99, 250, 'Stationery'),
('Monitor Stand', 'Adjustable monitor stand with storage', 44.99, 60, 'Office'),
('Webcam HD', '1080p webcam with built-in microphone', 79.99, 120, 'Electronics'),
('Headphones', 'Noise-cancelling over-ear headphones', 199.99, 90, 'Electronics'),
('Phone Stand', 'Adjustable phone stand for desk', 14.99, 400, 'Accessories'),
('Cable Organizer', 'Cable management box', 12.99, 500, 'Accessories'),
('External SSD 1TB', 'Portable SSD with USB 3.2', 149.99, 70, 'Electronics'),
('Desk Mat', 'Large desk mat for keyboard and mouse', 34.99, 150, 'Office');

-- Insert test orders
INSERT INTO orders (customer_id, total_amount, status, order_date) VALUES
(1, 1419.97, 'completed', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(2, 89.99, 'completed', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(3, 279.96, 'shipped', DATE_SUB(NOW(), INTERVAL 3 DAY)),
(4, 1549.96, 'processing', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(5, 44.99, 'completed', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(1, 199.99, 'pending', NOW()),
(6, 129.97, 'completed', DATE_SUB(NOW(), INTERVAL 7 DAY)),
(7, 349.97, 'completed', DATE_SUB(NOW(), INTERVAL 6 DAY)),
(8, 59.99, 'cancelled', DATE_SUB(NOW(), INTERVAL 8 DAY)),
(9, 1679.94, 'completed', DATE_SUB(NOW(), INTERVAL 10 DAY));

-- Insert order items
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
-- Order 1 (John Doe)
(1, 1, 1, 1299.99),
(1, 2, 2, 29.99),
(1, 4, 2, 49.99),
-- Order 2 (Jane Smith)
(2, 3, 1, 89.99),
-- Order 3 (Bob Johnson)
(3, 5, 2, 59.99),
(3, 6, 4, 39.99),
-- Order 4 (Alice Williams)
(4, 1, 1, 1299.99),
(4, 11, 1, 199.99),
(4, 4, 1, 49.99),
-- Order 5 (Charlie Brown)
(5, 9, 1, 44.99),
-- Order 6 (John Doe - second order)
(6, 11, 1, 199.99),
-- Order 7 (Diana Davis)
(7, 7, 3, 19.99),
(7, 8, 2, 24.99),
(7, 6, 1, 39.99),
-- Order 8 (Eve Martinez)
(8, 10, 2, 79.99),
(8, 14, 2, 149.99),
-- Order 9 (Frank Garcia)
(9, 5, 1, 59.99),
-- Order 10 (Grace Lee)
(10, 1, 1, 1299.99),
(10, 3, 1, 89.99),
(10, 2, 2, 29.99),
(10, 10, 1, 79.99),
(10, 14, 1, 149.99);

-- Create some useful views
CREATE OR REPLACE VIEW customer_order_summary AS
SELECT 
    c.id,
    c.first_name,
    c.last_name,
    c.email,
    COUNT(o.id) as total_orders,
    COALESCE(SUM(o.total_amount), 0) as total_spent,
    MAX(o.order_date) as last_order_date
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
GROUP BY c.id, c.first_name, c.last_name, c.email;

CREATE OR REPLACE VIEW product_sales_summary AS
SELECT 
    p.id,
    p.name,
    p.category,
    p.price,
    p.stock_quantity,
    COALESCE(SUM(oi.quantity), 0) as total_sold,
    COALESCE(SUM(oi.quantity * oi.unit_price), 0) as total_revenue
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.name, p.category, p.price, p.stock_quantity;

-- Display summary
SELECT 'Test data loaded successfully!' as message;
SELECT COUNT(*) as customer_count FROM customers;
SELECT COUNT(*) as product_count FROM products;
SELECT COUNT(*) as order_count FROM orders;
SELECT COUNT(*) as order_item_count FROM order_items;