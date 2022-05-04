rule code_hta {

	meta:
		type = "code/hta"
        score = 10

    strings:
        $hta = "<hta:application " nocase

	condition:
		$hta
}

rule code_html_with_script {

	meta:
		type = "code/hta"
        score = 10

    strings:
        $html_start = "<html" nocase
        $html_end = "</html" nocase
        $script = "<script" nocase
        $lang_js1 = "language=\"javascript\"" nocase
        $lang_js2 = "language=\"jscript\"" nocase
        $lang_js3 = "language=\"js\"" nocase
        $lang_vbs1 = "language=\"vbscript\"" nocase
        $lang_vbs2 = "language=\"vb\"" nocase

	condition:
		($html_start in (0..256)
        or $html_end in (filesize-256..filesize))
        and $script
        and 1 of ($lang*)
}

rule code_htc {

	meta:
		type = "code/htc"
        score = 15

    strings:
        $component1 = "public:component " nocase
        $component2 = "/public:component" nocase
        $script = "<script" nocase
        $lang_js1 = "language=\"javascript\"" nocase
        $lang_js2 = "language=\"jscript\"" nocase
        $lang_js3 = "language=\"js\"" nocase
        $lang_vbs1 = "language=\"vbscript\"" nocase
        $lang_vbs2 = "language=\"vb\"" nocase

	condition:
		all of ($component*)
        and $script
        and 1 of ($lang*)
}

rule code_javascript_1 {
    meta:
        type = "code/javascript"

    strings:
        $script = "<script" nocase
        $lang_js1 = "language=\"javascript\"" nocase
        $lang_js2 = "language=\"jscript\"" nocase
        $lang_js3 = "language=\"js\"" nocase
        $lang_js4 = "type=\"text/javascript\"" nocase

    condition:
        $script
        and 1 of ($lang*)
}

rule code_javascript_2 {
    meta:
        type = "code/javascript"

    strings:
        $strong_js1 = /function([ \t]*|[ \t]+[\w|_]+[ \t]*)\([\w_ \t,]*\)[ \t\n\r]*{/
        $strong_js2 = /\beval[ \t]*\("/
        $strong_js3 = /new[ \t]+ActiveXObject\("/
        $strong_js4 = /xfa\.((resolve|create)Node|datasets|form)"/
        $strong_js5 = /\.oneOfChild"/
        $strong_js6 = /unescape\(/
        $strong_js7 = /\.createElement\(/
        $strong_js8 = /submitForm\("/
        $strong_js9 = /document\.write\(/
        $strong_js10 = /setTimeout\(/

        $weak_js1 = /var /
        $weak_js2 = /String\.(fromCharCode|raw)\(/
        $weak_js3 = /Math\.(round|pow|sin|cos)\(/
        $weak_js4 = /(isNaN|isFinite|parseInt|parseFloat)\(/
        $weak_js5 = /WSH/
        $weak_js6 = /(document|window)\[/
        $weak_js7 = /this\.[\w]+/

    condition:
        2 of ($strong_js*)
        or (1 of ($strong_js*)
            and 2 of ($weak_js*))
}

rule code_html {

	meta:
		type = "code/html"

    strings:
        $html_doctype = "<!doctype html>" nocase
        $html_start = "<html" nocase
        $html_end = "</html" nocase

	condition:
		$html_doctype in (0..256)
		or $html_start in (0..256)
        or $html_end in (filesize-256..filesize)
}

rule code_html_with_js {

	meta:
		type = "code/hta"
        score = 10

    condition:
		code_html and 1 of (code_javascript*)
}
