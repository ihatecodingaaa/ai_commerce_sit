import React from "react";
import { Link, useParams } from "wouter";
import { PRODUCTS } from "@/data/products";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

export default function ProductDetail() {
  const params = useParams();
  const productId = parseInt(params.id || "1", 10);
  const product = PRODUCTS.find((p) => p.id === productId) || PRODUCTS[0];

  return (
    <div className="page-wrap">
      <Header />
      <main className="content">
        <Link href="/products" className="back-link">
          &larr; Back to products
        </Link>
        <div className="detail-grid animate-in">
          <div className="detail-thumb">
            <img src={product.image} alt={product.name} />
          </div>
          <div>
            <span className="category-badge">{product.category}</span>
            <h1 style={{ marginTop: "0.5rem" }}>{product.name}</h1>
            <div className="stars" style={{ marginBottom: "0.8rem" }}>
              &#9733;&#9733;&#9733;&#9733;&#9734;{" "}
              <span className="muted" style={{ fontSize: "0.85rem" }}>
                ({product.reviewCount} {product.reviewCount === 1 ? "review" : "reviews"})
              </span>
            </div>
            <p>{product.description}</p>
            <div className="price" style={{ fontSize: "1.4rem", margin: "1rem 0" }}>
              ${product.price.toFixed(2)}
            </div>
            <p className="muted">
              <Link href="/login" style={{ textDecoration: "underline" }}>Log in</Link> to add this to your cart or leave a review.
            </p>
          </div>
        </div>

        <h2 style={{ marginTop: "2rem" }}>Reviews</h2>
        <ul className="review-list">
          {product.reviews && product.reviews.length > 0 ? (
            product.reviews.map((rev) => (
              <li key={rev.id} className="review-card">
                <div className="review-head">
                  <span className={`avatar ${rev.presetClass}`}>{rev.avatar}</span>
                  <strong>{rev.author}</strong>
                  <span className="stars review-stars" style={{ fontSize: "0.75rem", marginLeft: "auto" }}>
                    {"★".repeat(rev.rating)}{"☆".repeat(5 - rev.rating)}
                  </span>
                </div>
                <p className="review-body-text">{rev.comment}</p>
              </li>
            ))
          ) : (
            <li className="empty-state">
              No reviews yet &mdash; be the first to share your thoughts.
            </li>
          )}
        </ul>
      </main>
      <Footer />
    </div>
  );
}
