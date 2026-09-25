on run argv
	set existingText to ""
	if (count of argv) > 0 then
		set existingText to item 1 of argv
	end if
	set theResult to display dialog "Pane description:" default answer existingText with title "Pane Description" buttons {"Cancel", "Save"} default button "Save" cancel button "Cancel"
	return text returned of theResult
end run
