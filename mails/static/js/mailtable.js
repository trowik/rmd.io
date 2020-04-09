(function (){

    var isPageBeingRefreshed = false

    window.onbeforeunload = function() {
        isPageBeingRefreshed = true
    }

    $.ajaxSetup({
         beforeSend: function(xhr, settings) {
             function getCookie(name) {
                 var cookieValue = null
                 if (document.cookie && document.cookie !== '') {
                     var cookies = document.cookie.split(';')
                     for (var i = 0; i < cookies.length; i++) {
                         var cookie = jQuery.trim(cookies[i])
                         if (cookie.substring(0, name.length + 1) == (name + '=')) {
                             cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
                             break;
                        }
                    }
                }
                return cookieValue;
             }
             if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
                 xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'))
             }
         },
        error: function(jqXHR, textStatus, errorThrown) {
            if (!isPageBeingRefreshed) {
                var message = 'Ooops, something went wrong'
                if (jqXHR.status == 404) {
                    message = '404 - Page not found'
                }
                addNotification({
                    type:'danger',
                    text: message
                })
                $('.modal').modal('hide')
            }
        }
    })

    function newTime(evt) {
        var due = $(evt.target).find('input').val()
        var id  = $(evt.target).closest('tr').attr('id')
        $.post(
            '/mails/update/' + id + '/',
            {
                'due': due
            }
        ).done( function() {
            var duefield = $('#due-' + id)
            duefield.text(due)
        })
    }

    function initiateSearch() {
        $('.search').keyup(function() {
            var key = $(this).val()
            var regex = new RegExp(key, 'i')
            $('.item').each( function() {
                var subject = $(this).find('.subject').text()
                var sent = $(this).find('.sent').text()
                var due = $(this).find('.due').text()
                var texts = [subject, sent, due]
                if (regex.test(texts.join(' '))) {
                    $(this).show()
                }
                else {
                    $(this).hide()
                }
            })
        })
    }

    function initiate() {
        $('.add-popover').popover('destroy')
        $('.add-popover').popover({html : true, trigger : 'hover'})
        initiateSearch()
    }

    function refresh() {
        // Do not poll when datepicker, popover or search is active
        if (
            $('.bootstrap-datetimepicker-widget').is(':visible') ||
            $('.search').val() ||
            $('.popover').is(':visible')
        ){
            return
        }
        $.ajax({
            url: '/mails/table/',
            success: function(data) {
                $('#list').html(data)
                initiate()
            }
        })
    }

    function scheduleRefresh(){
        refresh()
        setTimeout(scheduleRefresh, 10 * 1000)
    }

    initiate()
    scheduleRefresh()

})();
