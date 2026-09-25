// Point this at your backend. Defaults to localhost:8000 for local dev.
const API_BASE_URL = window.API_BASE_URL || "http://localhost:8000";

const state = {
  token: localStorage.getItem("cf_token") || null,
  categories: [],
  activeCategory: null,
  cart: { items: [], subtotal: 0 },
  selectedProductId: null,
};

// ---------- API helpers ----------
async function api(path, { method = "GET", body, auth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const errJson = await resp.json();
      detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
    } catch (_) {}
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

// ---------- Small rendering helpers ----------
function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function ratingText(p) {
  return p.avg_rating ? `★ ${Number(p.avg_rating).toFixed(1)} (${p.review_count} review${p.review_count === 1 ? "" : "s"})` : "No reviews yet";
}

function productCard(p, reasonLabel) {
  const lowStock = p.stock_quantity > 0 && p.stock_quantity <= 5;
  const outOfStock = p.stock_quantity === 0;
  const safeId = escapeHtml(p.id);

  return `
    <article class="card">
      <button class="product-name-btn" onclick="openProductDetails('${safeId}')" title="View product details">
        ${escapeHtml(p.name)}
      </button>
      <div class="desc">${escapeHtml(p.description || "")}</div>
      <div class="meta">${escapeHtml(ratingText(p))}</div>
      ${reasonLabel ? `<div class="reason">${escapeHtml(reasonLabel)}</div>` : ""}
      ${outOfStock ? `<div class="stock-low">Out of stock</div>` : lowStock ? `<div class="stock-low">Only ${p.stock_quantity} left</div>` : `<div class="stock-ok">In stock: ${p.stock_quantity}</div>`}
      <div class="price-row">
        <span class="price">${money(p.price)}</span>
        <div class="card-actions">
          <button class="secondary" onclick="openProductDetails('${safeId}')">Details</button>
          <button ${outOfStock ? "disabled" : ""} onclick="addToCart('${safeId}')">Add</button>
        </div>
      </div>
    </article>
  `;
}

// ---------- Product details / FE-10 ----------
window.openProductDetails = async (productId) => {
  state.selectedProductId = productId;
  const modal = document.getElementById("product-modal");
  const content = document.getElementById("product-details-content");

  modal.classList.remove("hidden");
  content.innerHTML = `<div class="loading">Loading product details...</div>`;

  try {
    // Use the existing backend detail endpoint.
    const product = await api(`/products/${encodeURIComponent(productId)}`);

    // Reviews are public, so no login is needed to view them.
    const reviews = await api(`/products/${encodeURIComponent(productId)}/reviews`);

    document.getElementById("product-modal-title").textContent = product.name;

    const outOfStock = product.stock_quantity === 0;
    const lowStock = product.stock_quantity > 0 && product.stock_quantity <= 5;

    const reviewsHtml = reviews.length
      ? reviews
          .map(
            (review) => `
              <div class="review-item">
                <div class="review-top">
                  <strong>${"★".repeat(review.rating)}${"☆".repeat(5 - review.rating)}</strong>
                  <span>${new Date(review.created_at).toLocaleString()}</span>
                </div>
                <p>${escapeHtml(review.comment || "No comment")}</p>
              </div>
            `
          )
          .join("")
      : `<p class="muted">No reviews yet. Be the first to review this product after purchase.</p>`;

    content.innerHTML = `
      <div class="detail-main">
        <div class="detail-info">
          <div class="detail-badge">SKU: ${escapeHtml(product.sku)}</div>
          <h2>${escapeHtml(product.name)}</h2>
          <p class="detail-description">${escapeHtml(product.description || "No description available.")}</p>

          <div class="detail-rating">
            <span>${escapeHtml(ratingText(product))}</span>
          </div>

          <div class="detail-price">${money(product.price)}</div>

          <div class="detail-stock ${outOfStock ? "danger" : lowStock ? "warning" : "ok"}">
            ${outOfStock ? "Out of stock" : lowStock ? `Only ${product.stock_quantity} left in stock` : `${product.stock_quantity} available in stock`}
          </div>

          <div class="detail-actions">
            <button ${outOfStock ? "disabled" : ""} onclick="addToCartFromDetails('${escapeHtml(product.id)}')">
              ${outOfStock ? "Out of stock" : "Add to Cart"}
            </button>
          </div>
        </div>
      </div>

      <section class="reviews-section">
        <div class="reviews-heading">
          <h3>Customer Reviews</h3>
          <span>${reviews.length} review${reviews.length === 1 ? "" : "s"}</span>
        </div>
        <div class="reviews-list">${reviewsHtml}</div>
      </section>
    `;
  } catch (e) {
    document.getElementById("product-modal-title").textContent = "Product Details";
    content.innerHTML = `
      <div class="error-box">
        <strong>Unable to load product details.</strong>
        <p>${escapeHtml(e.message)}</p>
        <button onclick="openProductDetails('${escapeHtml(productId)}')">Try again</button>
      </div>
    `;
  }
};

window.addToCartFromDetails = async (productId) => {
  await window.addToCart(productId);
};

function closeProductDetails() {
  document.getElementById("product-modal").classList.add("hidden");
  state.selectedProductId = null;
}

// ---------- Categories and catalog ----------
async function renderCategories() {
  state.categories = await api("/categories");
  const bar = document.getElementById("category-bar");
  bar.innerHTML =
    `<div class="category-chip ${!state.activeCategory ? "active" : ""}" onclick="selectCategory(null)">All</div>` +
    state.categories
      .map(
        (c) =>
          `<div class="category-chip ${state.activeCategory === c.id ? "active" : ""}" onclick="selectCategory('${escapeHtml(c.id)}')">${escapeHtml(c.name)}</div>`
      )
      .join("");
}

async function renderProducts() {
  const search = document.getElementById("search-input").value.trim();
  const params = new URLSearchParams();
  if (state.activeCategory) params.set("category_id", state.activeCategory);
  if (search) params.set("search", search);

  const products = await api(`/products?${params.toString()}`);
  document.getElementById("products-grid").innerHTML =
    products.map((p) => productCard(p)).join("") || "<p>No products found.</p>";
}

async function renderRecommendations() {
  const view = document.getElementById("recs-view");
  if (!state.token) {
    view.classList.add("hidden");
    return;
  }
  try {
    const recs = await api("/recommendations/for-me?limit=6", { auth: true });
    if (!recs.length) {
      view.classList.add("hidden");
      return;
    }
    view.classList.remove("hidden");
    document.getElementById("recs-grid").innerHTML = recs
      .map((r) => productCard(r.product, `Suggested: ${r.reason}`))
      .join("");
  } catch (e) {
    view.classList.add("hidden");
  }
}

// ---------- Cart ----------
async function renderCart() {
  if (!state.token) {
    state.cart = { items: [], subtotal: 0 };
  } else {
    try {
      state.cart = await api("/cart", { auth: true });
    } catch (e) {
      // If an old/expired token is stored, clear it and show guest state.
      state.token = null;
      localStorage.removeItem("cf_token");
      state.cart = { items: [], subtotal: 0 };
      updateAuthUI();
    }
  }

  document.getElementById("cart-count").textContent = state.cart.items.reduce((sum, i) => sum + i.quantity, 0);
  document.getElementById("cart-subtotal").textContent = money(state.cart.subtotal);
  document.getElementById("cart-items").innerHTML =
    state.cart.items
      .map(
        (i) => `
      <div class="cart-line">
        <span>${escapeHtml(i.product_name)} × ${i.quantity}</span>
        <span>${money(i.line_total)} <span class="remove" onclick="removeFromCart('${escapeHtml(i.product_id)}')">remove</span></span>
      </div>`
      )
      .join("") || "<p>Your cart is empty.</p>";
}

// ---------- Auth ----------
function updateAuthUI() {
  document.getElementById("auth-status").textContent = state.token ? "Signed in" : "Not signed in";
  document.getElementById("login-btn").textContent = state.token ? "Sign out" : "Sign in";
}

async function renderOrders() {
  const view = document.getElementById("orders-view");
  if (!state.token) {
    view.classList.add("hidden");
    return;
  }
  try {
    const orders = await api("/orders", { auth: true });
    view.classList.remove("hidden");
    document.getElementById("orders-list").innerHTML =
      orders.length
        ? orders
            .map(
              (o) => `
      <div class="order-card">
        <div><strong>Order #${escapeHtml(o.id.slice(0, 8))}</strong><div>${new Date(o.created_at).toLocaleString()}</div></div>
        <div><strong>${money(o.total)}</strong><div class="status">${escapeHtml(o.status)}</div></div>
      </div>`
            )
            .join("")
        : "<p>No orders yet.</p>";
  } catch (e) {
    view.classList.add("hidden");
  }
}

// ---------- Actions exposed globally ----------
window.selectCategory = async (id) => {
  state.activeCategory = id;
  await renderCategories();
  await renderProducts();
};

window.addToCart = async (productId) => {
  if (!state.token) {
    openLoginModal();
    return;
  }

  try {
    await api("/cart/items", {
      method: "POST",
      auth: true,
      body: { product_id: productId, quantity: 1 },
    });
    await renderCart();
    document.getElementById("cart-drawer").classList.remove("hidden");
  } catch (e) {
    alert(`Could not add product to cart: ${e.message}`);
  }
};

window.removeFromCart = async (productId) => {
  try {
    await api(`/cart/items/${encodeURIComponent(productId)}`, { method: "DELETE", auth: true });
    await renderCart();
  } catch (e) {
    alert(`Could not remove product: ${e.message}`);
  }
};

function openLoginModal() {
  document.getElementById("login-modal").classList.remove("hidden");
  document.getElementById("login-message").textContent = "";
}

// ---------- Event listeners ----------
document.getElementById("login-btn").addEventListener("click", async () => {
  if (state.token) {
    state.token = null;
    localStorage.removeItem("cf_token");
    updateAuthUI();
    await renderCart();
    await renderRecommendations();
    document.getElementById("orders-view").classList.add("hidden");
  } else {
    openLoginModal();
  }
});

document.getElementById("close-login").addEventListener("click", () => {
  document.getElementById("login-modal").classList.add("hidden");
});

document.getElementById("close-product").addEventListener("click", closeProductDetails);

document.getElementById("product-modal").addEventListener("click", (event) => {
  if (event.target.id === "product-modal") closeProductDetails();
});

async function handleAuth(pathSuffix) {
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const msg = document.getElementById("login-message");
  msg.textContent = "";

  try {
    if (pathSuffix === "register") {
      await api("/auth/register", {
        method: "POST",
        body: { email, password, full_name: "" },
      });
    }

    const tokenResp = await api("/auth/login", {
      method: "POST",
      body: { email, password },
    });

    state.token = tokenResp.access_token;
    localStorage.setItem("cf_token", state.token);
    document.getElementById("login-modal").classList.add("hidden");
    updateAuthUI();
    await renderCart();
    await renderRecommendations();
    await renderOrders();
  } catch (e) {
    msg.textContent = e.message;
  }
}

document.getElementById("do-login").addEventListener("click", () => handleAuth("login"));
document.getElementById("do-register").addEventListener("click", () => handleAuth("register"));

document.getElementById("cart-btn").addEventListener("click", () => {
  document.getElementById("cart-drawer").classList.toggle("hidden");
});

document.getElementById("close-cart").addEventListener("click", () => {
  document.getElementById("cart-drawer").classList.add("hidden");
});

document.getElementById("checkout-btn").addEventListener("click", async () => {
  const msg = document.getElementById("checkout-message");
  msg.style.color = "var(--danger)";
  msg.textContent = "";

  if (!state.token) {
    openLoginModal();
    return;
  }

  if (!state.cart.items.length) {
    msg.textContent = "Your cart is empty.";
    return;
  }

  try {
    const idempotencyKey = `checkout-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const order = await api("/orders/checkout", {
      method: "POST",
      auth: true,
      body: { idempotency_key: idempotencyKey },
    });

    msg.style.color = "#4caf50";
    msg.textContent = `Order placed! Total ${money(order.total)}.`;
    await renderCart();
    await renderProducts();
    await renderRecommendations();
    await renderOrders();
  } catch (e) {
    msg.textContent = e.message;
  }
});

let searchDebounce;
document.getElementById("search-input").addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(renderProducts, 300);
});

document.getElementById("orders-btn").addEventListener("click", async () => {
  if (!state.token) {
    openLoginModal();
    return;
  }
  await renderOrders();
  document.getElementById("orders-view").scrollIntoView({ behavior: "smooth" });
});

// Close modals with Escape.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!document.getElementById("product-modal").classList.contains("hidden")) closeProductDetails();
  if (!document.getElementById("login-modal").classList.contains("hidden")) {
    document.getElementById("login-modal").classList.add("hidden");
  }
});

// ---------- Boot ----------
(async function init() {
  try {
    updateAuthUI();
    await renderCategories();
    await renderProducts();
    await renderCart();
    await renderRecommendations();
  } catch (e) {
    document.getElementById("products-grid").innerHTML = `<div class="error-box"><strong>Unable to load CommerceFlow.</strong><p>${escapeHtml(e.message)}</p></div>`;
  }
})();
