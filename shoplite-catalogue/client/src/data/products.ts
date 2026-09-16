export interface Product {
  id: number;
  name: string;
  category: string;
  description: string;
  price: number;
  rating: number;
  reviewCount: number;
  image: string;
  reviews?: {
    id: number;
    author: string;
    avatar: string;
    presetClass: string;
    rating: number;
    comment: string;
  }[];
}

export const PRODUCTS: Product[] = [
  {
    id: 1,
    name: "Aurora Wireless Earbuds",
    category: "Audio",
    description: "Compact true-wireless earbuds with 24h battery life and active noise cancellation.",
    price: 59.99,
    rating: 4,
    reviewCount: 1,
    image: "/manus-storage/aurora-wireless-earbuds_6eba11c0.png",
    reviews: [
      {
        id: 1,
        author: "bob.customer",
        avatar: "🦉",
        presetClass: "avatar-preset-2",
        rating: 5,
        comment: "Great sound and the battery really does last all day. Shipping was fast too."
      }
    ]
  },
  {
    id: 2,
    name: "Pulse Fitness Band",
    category: "Wearables",
    description: "Lightweight fitness tracker with heart-rate monitoring and 7-day battery.",
    price: 34.99,
    rating: 4,
    reviewCount: 0,
    image: "/manus-storage/pulse-fitness-band_a5ac6b94.png",
    reviews: []
  },
  {
    id: 3,
    name: "Nimbus Portable SSD 1TB",
    category: "Storage",
    description: "USB-C portable SSD, up to 1050MB/s read speeds, shock resistant.",
    price: 89.99,
    rating: 4,
    reviewCount: 1,
    image: "/manus-storage/nimbus-portable-ssd_4c46cd20.jpg",
    reviews: [
      {
        id: 2,
        author: "alice.customer",
        avatar: "🐼",
        presetClass: "avatar-preset-1",
        rating: 4,
        comment: "Fast drive, feels well built. Wish it came with a carrying pouch."
      }
    ]
  },
  {
    id: 4,
    name: "Lumen Smart Desk Lamp",
    category: "Home",
    description: "Adjustable smart desk lamp with app-controlled brightness and color temperature.",
    price: 29.99,
    rating: 4,
    reviewCount: 0,
    image: "/manus-storage/lumen-smart-desk-lamp_eca82156.jpg",
    reviews: []
  },
  {
    id: 5,
    name: "Voyager Travel Charger",
    category: "Accessories",
    description: "65W GaN USB-C charger with three ports for laptops, phones, and tablets.",
    price: 19.99,
    rating: 4,
    reviewCount: 0,
    image: "/manus-storage/voyager-travel-charger_93ef5706.jpg",
    reviews: []
  },
  {
    id: 6,
    name: "Echo Mini Bluetooth Speaker",
    category: "Audio",
    description: "Palm-sized Bluetooth speaker with surprisingly big sound and IPX6 rating.",
    price: 24.99,
    rating: 4,
    reviewCount: 0,
    image: "/manus-storage/echo-mini-bluetooth-speaker_3cca42b7.jpg",
    reviews: []
  }
];

export const LOGO_SVG = "/manus-storage/logo_be7433c6.svg";
