const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const navigation = document.querySelector(".nav-links");

if (mobileMenuBtn && navigation) {
    mobileMenuBtn.addEventListener("click", function () {
        navigation.classList.toggle("mobile-open");
        mobileMenuBtn.setAttribute("aria-expanded", navigation.classList.contains("mobile-open"));
    });
}