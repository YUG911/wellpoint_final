// =========================
// GET ELEMENTS
// =========================

const searchInput =
    document.getElementById("searchInput");

const locationInput =
    document.getElementById("locationInput");

const useLocationBtn =
    document.getElementById("useLocationBtn");

const userLatInput =
    document.getElementById("userLatInput");

const userLngInput =
    document.getElementById("userLngInput");

const searchForm =
    document.getElementById("searchForm") ||
    document.querySelector(".search-box");

const searchButton =
    document.getElementById("searchButton");

const doctorCards =
    document.querySelectorAll(".doctor-card");

const specializationFilters =
    document.querySelectorAll(".specialization-filter");
const locationFilters = document.querySelectorAll(".location-filter");

const availabilityFilters =
    document.querySelectorAll(".availability-filter");

const experienceFilters =
    document.querySelectorAll(
        'input[name="experience"]'
    );

const feeFilters =
    document.querySelectorAll(
        'input[name="fee"]'
    );

const doctorCount =
    document.getElementById("doctorCount");

const noResults = document.querySelector(".no-results");

const clearFilters =
    document.getElementById("clearFilters");

const resetSearch =
    document.getElementById("resetSearch");

const sortDoctors =
    document.getElementById("sortDoctors");

const doctorsList =
    document.getElementById("doctorsList");

const mobileMenuBtn =
    document.getElementById("mobileMenuBtn");

const mobileMenu =
    document.getElementById("mobileMenu");


// =========================
// SEARCH + FILTER FUNCTION
// =========================

function filterDoctors() {

    const searchValue =
        searchInput.value.toLowerCase();

    const locationValue =
        locationInput.value.toLowerCase();


    // Selected specializations

    const selectedSpecializations =
        Array.from(specializationFilters)
            .filter(filter => filter.checked)
            .map(filter => filter.value.toLowerCase());
    const selectedLocations = Array.from(locationFilters).filter(filter => filter.checked).map(filter => filter.value.toLowerCase());


    // Selected availability

    const selectedAvailability =
        Array.from(availabilityFilters)
            .filter(filter => filter.checked)
            .map(filter => filter.value);


    // Selected experience

    const selectedExperience =
        document.querySelector(
            'input[name="experience"]:checked'
        ).value;


    // Selected fee

    const selectedFeeInput = document.querySelector('input[name="fee"]:checked');
    const selectedFee = selectedFeeInput ? selectedFeeInput.value : 'all';


    let visibleDoctors = 0;


    doctorCards.forEach(function (card) {

        const name =
            card.dataset.name.toLowerCase();

        const specialization =
            card.dataset.specialization;

        const location =
            card.dataset.location.toLowerCase();

        const experience =
            Number(card.dataset.experience);

        const fee =
            Number(card.dataset.fee);

        const availability = (card.dataset.availability || "").split(" ");


        // SEARCH MATCH

        const matchesSearch =
            name.includes(searchValue) ||
            specialization
                .toLowerCase()
                .includes(searchValue);


        // LOCATION MATCH (Respects geolocation and manual city filters)

        const isGeolocated = (userLatInput && userLatInput.value !== "" && userLngInput && userLngInput.value !== "") ||
                             (locationInput && (locationInput.dataset.geolocated === "true" ||
                                                locationValue === "current location" ||
                                                locationValue === "my location"));

        const matchesLocation =
            isGeolocated ||
            locationValue === "" ||
            location.includes(locationValue);


        // SPECIALIZATION MATCH

        const matchesSpecialization =
            selectedSpecializations.length === 0 ||
            selectedSpecializations.some(value => specialization.toLowerCase().includes(value));
        const matchesSelectedLocation = selectedLocations.length === 0 || selectedLocations.some(value => location.includes(value));


        // EXPERIENCE MATCH

        let matchesExperience = true;


        if (selectedExperience === "1-5") {

            matchesExperience =
                experience >= 1 &&
                experience <= 5;

        }

        else if (selectedExperience === "5-10") {

            matchesExperience =
                experience >= 5 &&
                experience <= 10;

        }

        else if (selectedExperience === "10+") {

            matchesExperience =
                experience >= 10;

        }


        // FEE MATCH

        let matchesFee = true;


        if (selectedFee === "500") {

            matchesFee = fee < 500;

        }

        else if (selectedFee === "1000") {

            matchesFee =
                fee >= 500 &&
                fee <= 1000;

        }

        else if (selectedFee === "above1000") {

            matchesFee =
                fee > 1000;

        }


        // AVAILABILITY MATCH

        const matchesAvailability =
            selectedAvailability.length === 0 ||

            selectedAvailability.some(
                value =>
                    availability.includes(value)
            );


        // FINAL RESULT

        if (
            matchesSearch &&
            matchesLocation &&
            matchesSelectedLocation &&
            matchesSpecialization &&
            matchesExperience &&
            matchesFee &&
            matchesAvailability
        ) {

            card.style.display = "grid";

            visibleDoctors++;

        }

        else {

            card.style.display = "none";

        }

    });


    // UPDATE COUNT

    doctorCount.textContent =
        visibleDoctors;


    // NO RESULTS

    if (visibleDoctors === 0) {

        if (noResults) noResults.style.display = "block";

    }

    else {

        if (noResults) noResults.style.display = "none";

    }

}


// =========================
// SEARCH BUTTON
// =========================

if (searchButton) searchButton.addEventListener(
    "click",
    filterDoctors
);


// Live search

if (searchInput) searchInput.addEventListener(
    "input",
    filterDoctors
);

if (locationInput) locationInput.addEventListener(
    "input",
    filterDoctors
);


// =========================
// FILTER EVENTS
// =========================

specializationFilters.forEach(
    function (filter) {

        filter.addEventListener(
            "change",
            filterDoctors
        );

    }
);


availabilityFilters.forEach(
    function (filter) {

        filter.addEventListener(
            "change",
            filterDoctors
        );

    }
);

locationFilters.forEach(filter => filter.addEventListener("change", filterDoctors));


experienceFilters.forEach(
    function (filter) {

        filter.addEventListener(
            "change",
            filterDoctors
        );

    }
);


feeFilters.forEach(
    function (filter) {

        filter.addEventListener(
            "change",
            filterDoctors
        );

    }
);


// =========================
// CLEAR FILTERS
// =========================

if (clearFilters) clearFilters.addEventListener(
    "click",
    resetAll
);

if (resetSearch) resetSearch.addEventListener(
    "click",
    resetAll
);


function resetAll() {

    // Clear search

    searchInput.value = "";

    locationInput.value = "";

    if (userLatInput) userLatInput.value = "";
    if (userLngInput) userLngInput.value = "";
    if (locationInput) delete locationInput.dataset.geolocated;


    // Clear checkboxes

    specializationFilters.forEach(
        function (filter) {

            filter.checked = false;

        }
    );


    availabilityFilters.forEach(
        function (filter) {

            filter.checked = false;

        }
    );


    // Reset radio buttons

    const defaultExperience = document.querySelector('input[name="experience"][value="all"]');
    if (defaultExperience) defaultExperience.checked = true;


    const defaultFee = document.querySelector('input[name="fee"][value="all"]');
    if (defaultFee) defaultFee.checked = true;


    filterDoctors();

}


// =========================
// REAL-TIME GEOLOCATION
// =========================

if (useLocationBtn) {
    useLocationBtn.addEventListener("click", function () {
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser. Please enter your city manually in the search box.");
            return;
        }

        const originalHTML = useLocationBtn.innerHTML;
        useLocationBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span class="location-btn-text">Locating...</span>';
        useLocationBtn.disabled = true;

        navigator.geolocation.getCurrentPosition(
            function (position) {
                const lat = position.coords.latitude.toFixed(6);
                const lng = position.coords.longitude.toFixed(6);

                if (userLatInput) userLatInput.value = lat;
                if (userLngInput) userLngInput.value = lng;
                if (locationInput) {
                    locationInput.value = "Current Location";
                    locationInput.dataset.geolocated = "true";
                }

                useLocationBtn.innerHTML = originalHTML;
                useLocationBtn.disabled = false;

                if (searchForm) {
                    searchForm.submit();
                } else {
                    const params = new URLSearchParams(window.location.search);
                    params.set('user_lat', lat);
                    params.set('user_lng', lng);
                    params.set('location', 'Current Location');
                    window.location.search = params.toString();
                }
            },
            function (error) {
                useLocationBtn.innerHTML = originalHTML;
                useLocationBtn.disabled = false;
                let message = "Could not obtain your location.";
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        message = "Location permission was denied. You can search for doctors by entering your city in the location box.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        message = "Location information is currently unavailable. Please enter your city manually.";
                        break;
                    case error.TIMEOUT:
                        message = "The request to get your location timed out. Please try again or enter your city manually.";
                        break;
                }
                alert(message);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            }
        );
    });
}

// Clear coordinates if patient types a city manually
if (locationInput) {
    locationInput.addEventListener("input", function () {
        const val = locationInput.value.toLowerCase().trim();
        if (val !== "current location" && val !== "my location" && val !== "near me") {
            if (userLatInput) userLatInput.value = "";
            if (userLngInput) userLngInput.value = "";
            delete locationInput.dataset.geolocated;
        }
    });
}


// =========================
// SORT DOCTORS
// =========================

if (sortDoctors) sortDoctors.addEventListener(
    "change",
    function () {

        const cards =
            Array.from(doctorCards);


        cards.sort(function (a, b) {

            if (
                sortDoctors.value ===
                "experience"
            ) {

                return (
                    Number(
                        b.dataset.experience
                    )
                    -
                    Number(
                        a.dataset.experience
                    )
                );

            }


            if (
                sortDoctors.value ===
                "fee-low"
            ) {

                return (
                    Number(a.dataset.fee)
                    -
                    Number(b.dataset.fee)
                );

            }


            if (
                sortDoctors.value ===
                "fee-high"
            ) {

                return (
                    Number(b.dataset.fee)
                    -
                    Number(a.dataset.fee)
                );

            }


            return 0;

        });


        cards.forEach(
            function (card) {

                doctorsList.appendChild(card);

            }
        );

    }
);


// =========================
// MOBILE MENU
// =========================

if (mobileMenuBtn && mobileMenu) mobileMenuBtn.addEventListener(
    "click",
    function () {

        mobileMenu.classList.toggle("show");

    }
);
