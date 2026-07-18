document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.getElementById("theme-toggle");
  if (!toggle) return;

  toggle.addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-bs-theme") || "light";
    var next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-bs-theme", next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("pronotedz-theme", next);
  });
});
