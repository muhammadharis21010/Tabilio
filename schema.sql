CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  username VARCHAR(40) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('admin','waiter','kitchen','cashier') NOT NULL
);
CREATE TABLE IF NOT EXISTS restaurant_tables (
  id INT AUTO_INCREMENT PRIMARY KEY,
  label VARCHAR(30) NOT NULL,
  seats INT NOT NULL DEFAULT 4,
  status ENUM('free','occupied','needs_help') NOT NULL DEFAULT 'free'
);
CREATE TABLE IF NOT EXISTS categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL
);
CREATE TABLE IF NOT EXISTS menu_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  category_id INT NOT NULL,
  name VARCHAR(80) NOT NULL,
  description VARCHAR(255),
  price DECIMAL(10,2) NOT NULL,
  image_url VARCHAR(255),
  available TINYINT(1) NOT NULL DEFAULT 1,
  FOREIGN KEY (category_id) REFERENCES categories(id)
);
CREATE TABLE IF NOT EXISTS deals (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(80) NOT NULL,
  description VARCHAR(255),
  discount_percent DECIMAL(5,2) NOT NULL DEFAULT 0,
  active TINYINT(1) NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  table_id INT NOT NULL,
  status ENUM('placed','preparing','ready','served','billed') NOT NULL DEFAULT 'placed',
  notes VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (table_id) REFERENCES restaurant_tables(id)
);
CREATE TABLE IF NOT EXISTS order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  item_id INT NOT NULL,
  qty INT NOT NULL,
  customization VARCHAR(200),
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES menu_items(id)
);
CREATE TABLE IF NOT EXISTS payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL UNIQUE,
  subtotal DECIMAL(10,2) NOT NULL,
  discount DECIMAL(10,2) NOT NULL,
  tax DECIMAL(10,2) NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  method ENUM('cash','card','online') NOT NULL,
  paid_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(id)
);
CREATE TABLE IF NOT EXISTS feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,
  table_id INT NOT NULL,
  rating TINYINT NOT NULL,
  comment VARCHAR(500),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (table_id) REFERENCES restaurant_tables(id)
);
CREATE TABLE IF NOT EXISTS waiter_calls (
  id INT AUTO_INCREMENT PRIMARY KEY,
  table_id INT NOT NULL,
  reason VARCHAR(100),
  resolved TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (table_id) REFERENCES restaurant_tables(id)
);
INSERT INTO restaurant_tables (label, seats) VALUES ('Table 1',2),('Table 2',2),('Table 3',4),('Table 4',4),('Table 5',4),('Table 6',6),('Table 7',6),('Table 8',8);
INSERT INTO categories (name) VALUES ('Starters'),('Main Course'),('Drinks'),('Desserts');
INSERT INTO menu_items (category_id,name,description,price) VALUES
(1,'Chicken Wings','Crispy wings with hot garlic sauce',650),
(1,'French Fries','Golden fries with masala dust',350),
(1,'Garlic Bread','Toasted with herb butter',400),
(2,'Chicken Karahi','Traditional karahi with naan',1450),
(2,'Beef Burger','Grilled patty, cheese, fries',900),
(2,'Chicken Biryani','Aromatic rice with raita',700),
(2,'Alfredo Pasta','Creamy white sauce pasta',950),
(3,'Fresh Lime','Chilled lime soda',250),
(3,'Mint Margarita','Mint and lemon cooler',300),
(3,'Doodh Patti Chai','Hot, strong and creamy',150),
(4,'Chocolate Brownie','Warm brownie with ice cream',500),
(4,'Kheer','Traditional rice pudding',300);
INSERT INTO deals (title,description,discount_percent,active) VALUES
('Weekend Special','10% off on every order',10,1);
