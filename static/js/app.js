$(document).ready(function () {

    $('input[name="q"]').focus();

    //MultiSelect Dropdown Select
    $('#multiple-checkboxes-languages').multiselect({
        includeSelectAllOption: true,
    });

    //MultiSelect Dropdown Updates
    if (location.href.indexOf('signup') > -1) {
        $('button.multiselect > span').text('Select Spoken Languages');
        let o = '<option value="" selected="selected">Select Country / Region</option>';
        $('#multiple-checkboxes-location').prepend(o);
    }

    //Chat Info
    $('[data-chat-info-toggle]').on('click', function (e) {
        e.preventDefault()
        $('.chat-info').addClass('chat-info-visible');
    });
    $('[data-chat-info-close]').on('click', function (e) {
        e.preventDefault()
        $('.chat-info').removeClass('chat-info-visible');
    });

    //Profile Info
    $('[data-profile-edit]').on('click', function () {
        $('.main').addClass('main-visible');
    });

    //Toggle View
    $('[data-toggle-view]').on('click', function () {
        $('.main').toggleClass('main-visible');
    });
    
    //Backdrop
    $('.backdrop').on('click', function () {
        $('.backdrop').removeClass('backdrop-visible');
        $('.appnavbar-content').removeClass('appnavbar-content-visible');
        $('#appNavTab .nav-link').removeClass('active');
    });

});


