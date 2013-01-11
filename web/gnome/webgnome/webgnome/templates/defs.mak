### Mako defs.

<%def name="is_active(url)">
<%doc>
     Return True if the current request path is equal to ``url``.
</%doc>
    % if request.path == url:
        active
    % endif
</%def>


<%def name="form_control(field, help_text=None, label=None, hidden=False,
                         extra_classes=None, use_id=False, opts=None)">
<%doc>
    Render a Bootstrap form control around ``field``.
</%doc>
    <div class="control-group
                % if hidden:
                    hidden
                % endif
                % if extra_classes:
                    % for cls in extra_classes:
                        ${cls}
                    % endfor
                % endif
                ">

        % if label:
            <label class="control-label"> ${label} </label>
        % endif

        <div class="controls">
            ${field}
            <span class="help-inline">
                 % if help_text:
                    ${help_text | n}
                 % endif
            </span>
        </div>
    </div>
</%def>


<%def name="time_control(hour_label='Time (24-hour): ', help_text='')">
<%doc>
    Render a Bootstrap form control for a :class:`datetime.datetime` value,
    displaying only the time values (hour and minute).
</%doc>

    <div class="control-group">
        % if hour_label:
            <label class="control-label">${hour_label}</label>
        % endif

        <div class="controls">
        ${h.text("hour", class_="input-micro")} : ${h.text("minute", class_="input-micro")}
            <span class="help-inline">
                % if help_text:
                    ${help_text}
                % endif
            </span>
        </div>
    </div>
</%def>
