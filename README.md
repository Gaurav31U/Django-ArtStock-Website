# Artstock: E-commerce Website for Buying and Selling Art

Artstock is a Django-based e-commerce platform where artists can sell their artwork and customers can purchase it. The website provides a simple and user-friendly interface for both artists and customers to interact with the platform.

## Features

- **Artist Dashboard**: Artists can upload their artwork, manage their portfolio, and track sales.
- **Customer Dashboard**: Customers can browse artwork, purchase pieces, and manage their orders.
- **Simple UI**: Easy-to-navigate interface for both artists and customers.
- **Secure Transactions**: Safe and secure payment processing for buying and selling art.

## Prerequisites

- Python 3.x

## Installation

### Step 1: Install Python

Make sure you have Python 3 installed on your local machine. You can download it from [Python's official website](https://www.python.org/downloads/).

### Step 2: Install Django and Pillow

Open your terminal and run the following commands to install Django and Pillow:
```
pip install Django
pip install Pillow
```
### Step 3: Clone the Project

Clone the Artstock repository to your local machine:
```
git clone https://github.com/Gaurav31U/Django-ArtStock-Website.git
cd Django-ArtStock-Website
```
### Step 4: Run the Server

Navigate to the project directory and start the Django development server:
```
python manage.py runserver
```
### Step 5: Access the Website

Open your web browser and go to [http://127.0.0.1:8000](http://127.0.0.1:8000) to access the Artstock website.

## Usage

### For Artists

1. **Register/Login**: Artists can register or log in to their accounts.
2. **Upload Artwork**: Artists can upload images of their artwork along with descriptions and prices.
3. **Manage Portfolio**: Artists can view and manage their uploaded artwork.
4. **Track Sales**: Artists can track their sales and earnings.

### For Customers

1. **Browse Artwork**: Customers can browse the artwork available for sale.
2. **Purchase Artwork**: Customers can add artwork to their cart and proceed to checkout.
3. **Order Management**: Customers can view and manage their orders.

## Docker Setup

You can also set up and run the Artstock project using Docker. Follow the steps below:

### Step 1: Build the Docker Image

Build the Docker image using the following command:
```
docker build -t artstock .
```
### Step 2: Run the Docker Container

Run the Docker container using the following command:

```
docker run -p 8000:8000 artstock
```
### Step 3: Access the Website

Open your web browser and go to [http://127.0.0.1:8000](http://127.0.0.1:8000) to access the Artstock website.

## Contributing

If you would like to contribute to Artstock, please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Create a new Pull Request.



## Contact

For any inquiries or issues, please contact us at [gaurav319288@gmail.com](gaurav319288@gmail.com).

---

Thank you for using Artstock!