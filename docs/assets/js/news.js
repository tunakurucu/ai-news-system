document.addEventListener("DOMContentLoaded", function () {
    // Mobile menu
    const menuToggle = document.querySelector(".menu-toggle");
    const navLinks = document.querySelector(".nav-links");

    if (menuToggle && navLinks) {
        menuToggle.addEventListener("click", function () {
            const isOpen = navLinks.classList.toggle("open");
            menuToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });
    }

    // Home page search + category filtering
    const homeSearchInput = document.querySelector("#home-search-input");
    const newsCards = document.querySelectorAll(".news-card");
    const categoryButtons = document.querySelectorAll(".category-filter-btn");
    const categorySections = document.querySelectorAll(".category-section");
    let selectedCategory = "all";

    function filterHome() {
        const query = (homeSearchInput && homeSearchInput.value || "").toLowerCase();

        newsCards.forEach(function (card) {
            const text = card.dataset.search || "";
            const category = card.dataset.category || "genel";

            const matchesSearch = text.includes(query);
            const matchesCategory = selectedCategory === "all" || category === selectedCategory;

            card.style.display = matchesSearch && matchesCategory ? "" : "none";
        });

        categorySections.forEach(function (section) {
            const visibleCards = Array.from(section.querySelectorAll(".news-card")).filter(function (card) {
                return card.style.display !== "none";
            });
            section.style.display = visibleCards.length ? "" : "none";
        });
    }

    if (homeSearchInput) {
        homeSearchInput.addEventListener("input", filterHome);
    }

    if (categoryButtons && categoryButtons.length) {
        categoryButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                categoryButtons.forEach(function (btn) {
                    btn.classList.remove("active");
                });

                button.classList.add("active");
                selectedCategory = button.dataset.category;

                filterHome();
            });
        });
    }

    // Search page
    const searchInput = document.querySelector("#search-input");
    const resultsContainer = document.querySelector("#search-results");
    const searchDataEl = document.querySelector("#search-data");
    const resultsMeta = document.querySelector("#search-results-meta");

    if (searchInput && resultsContainer && searchDataEl) {
        let newsData = [];
        try {
            newsData = JSON.parse(searchDataEl.textContent) || [];
        } catch (e) {
            newsData = [];
        }

        function escapeHtml(str) {
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function formatPublished(item) {
            const raw = item.published_at || item.published || "";
            if (!raw) return "";
            const d = new Date(raw);
            if (isNaN(d.getTime())) return escapeHtml(raw);
            const months = [
                "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
            ];
            return d.getDate() + " " + months[d.getMonth()] + " " + d.getFullYear() +
                ", " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
        }

        function buildCard(item) {
            const card = document.createElement("article");
            card.className = "news-card";

            const category = item.category ? '<span class="category-label">' + escapeHtml(item.category.toUpperCase()) + "</span>" : "";
            const meta = [item.source, formatPublished(item)].filter(Boolean).join(" · ");
            const title = escapeHtml(item.title || "");
            const summary = escapeHtml(item.summary || "");
            const link = escapeHtml(item.link || "#");

            card.innerHTML =
                '<div class="news-card-body">' +
                '<div class="eyebrow-row">' + category + '<span class="source source-inline">' + escapeHtml(meta) + '</span></div>' +
                "<h3>" + title + "</h3>" +
                "<p>" + summary + "</p>" +
                '</div>' +
                '<div class="card-footer"><span class="source source-block">' + escapeHtml(meta) + '</span>' +
                '<a class="read-link" href="' + link + '" target="_blank" rel="noopener noreferrer">Haberi oku</a></div>';

            return card;
        }

        function showResults(items) {
            resultsContainer.innerHTML = "";
            if (resultsMeta) {
                const count = items ? items.length : 0;
                resultsMeta.textContent = count + " sonuç";
            }

            if (!items || !items.length) {
                resultsContainer.innerHTML = '<p class="empty-state">Sonuç bulunamadı.</p>';
                return;
            }

            const fragment = document.createDocumentFragment();
            items.forEach(function (item) {
                fragment.appendChild(buildCard(item));
            });
            resultsContainer.appendChild(fragment);
        }

        function filterSearch() {
            const query = (searchInput.value || "").toLowerCase();

            const filtered = newsData.filter(function (item) {
                const text = [
                    item.title || "",
                    item.summary || "",
                    item.category || "",
                    item.source || "",
                    item.published || ""
                ].join(" ").toLowerCase();

                return text.includes(query);
            });

            showResults(filtered);
        }

        showResults(newsData);
        searchInput.addEventListener("input", filterSearch);
    }
});
