const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const navigation = document.querySelector(".nav-links");

if (mobileMenuBtn && navigation) {
    mobileMenuBtn.addEventListener("click", function () {
        navigation.classList.toggle("mobile-open");
        mobileMenuBtn.setAttribute("aria-expanded", navigation.classList.contains("mobile-open"));
    });
}
// ==========================================
// HOMEPAGE DOCTOR SEARCH
// ==========================================

const homeSearchButton =
    document.getElementById("homeSearchButton");

const homeDoctorSearch =
    document.getElementById("homeDoctorSearch");

const homeSpecialization =
    document.getElementById("homeSpecialization");

const homeLocation =
    document.getElementById("homeLocation");


if (homeSearchButton) {

    homeSearchButton.addEventListener(
        "click",
        function () {

            const doctorSearch =
                homeDoctorSearch.value.trim();

            const specialization =
                homeSpecialization.value;

            const location =
                homeLocation.value.trim();


            // Create URL parameters

            const params =
                new URLSearchParams();


            // Doctor name or search text

            if (doctorSearch !== "") {

                params.set(
                    "search",
                    doctorSearch
                );

            }


            // Specialization

            if (specialization !== "") {

                params.set(
                    "specialization",
                    specialization
                );

            }


            // Location

            if (location !== "") {

                params.set(
                    "location",
                    location
                );

            }


            // Doctors page URL

            let doctorsURL =
                "pages/doctors.html";


            // Add search parameters if user entered something

            if (params.toString() !== "") {

                doctorsURL +=
                    "?" +
                    params.toString();

            }


            // Redirect to Doctors page

            window.location.href =
                doctorsURL;

        }
    );

}
