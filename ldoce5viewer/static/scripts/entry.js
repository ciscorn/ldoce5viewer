$(function(){
    $("a.illust").colorbox({
        transition: 'none',
        opacity: 0.75,
    });

    $("a[href*='/etymologies/']").colorbox({
        iframe: true,
        width: '70%',
        height: '70%',
        transition: 'none',
        opacity: 0.75,
    });

    $("a[href*='/word_families/']").colorbox({
        iframe: true,
        width: '75%',
        height: '85%',
        transition: 'none',
        opacity: 0.75,
    });
})

