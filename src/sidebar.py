# sidebar.py
#
# Copyright 2022 knuxify
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE X CONSORTIUM BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Except as contained in this notice, the name(s) of the above copyright
# holders shall not be used in advertising or otherwise to promote the sale,
# use or other dealings in this Software without prior written
# authorization.

from gi.repository import GObject, Gtk, GLib
import os.path

@Gtk.Template(resource_path='/app/drey/EarTag/ui/filelistitem.ui')
class EartagFileListItem(Gtk.Box):
    __gtype_name__ = 'EartagFileListItem'

    modified_icon = Gtk.Template.Child()
    coverart_image = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    filename_label = Gtk.Template.Child()
    _title = None
    file = None
    bindings = []

    def __init__(self, filelist):
        super().__init__()
        self.filelist = filelist
        self.connect('destroy', self.on_destroy)

    def bind_to_file(self, file):
        if self.bindings:
            for b in self.bindings:
                b.unbind()
        self.file = file

        self.bindings.append(self.file.bind_property('title', self, 'title',
            GObject.BindingFlags.SYNC_CREATE))
        self.bindings.append(self.file.bind_property('is-modified', self.modified_icon,
            'visible', GObject.BindingFlags.SYNC_CREATE))
        self.filename_label.set_label(os.path.basename(file.path))
        self.coverart_image.bind_to_file(file)

    def on_destroy(self, *args):
        if self.bindings:
            for b in self.bindings:
                b.unbind()
        self.file = None

    @Gtk.Template.Callback()
    def remove_item(self, *args):
        if self.filelist.file_manager.remove(self.file):
            self.on_destroy()

    @GObject.Property(type=str)
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        # TRANSLATORS: Placeholder for file sidebar items with no title set
        self.title_label.set_label(value or _('(No title)'))

class EartagFileList(Gtk.ListView):
    """List of opened tracks."""
    __gtype_name__ = 'EartagFileList'

    def __init__(self):
        super().__init__()
        self.sidebar_factory = Gtk.SignalListItemFactory()
        self.sidebar_factory.connect('setup', self.setup)
        self.sidebar_factory.connect('bind', self.bind)
        self.set_factory(self.sidebar_factory)
        self.add_css_class('navigation-sidebar')

    def set_file_manager(self, file_manager):
        self.file_manager = file_manager
        self.file_manager.connect('selection-override', self.handle_selection_override)

    def set_sidebar(self, sidebar):
        self.sidebar = sidebar

        # Set up sort model for sort button
        self.sort_model = Gtk.SortListModel(model=self.file_manager.files)
        self.sorter = Gtk.CustomSorter.new(self.sort_func, None)
        self.sort_model.set_sorter(self.sorter)

        # Set up filter model for search
        self.filter_model = Gtk.FilterListModel(model=self.sort_model)
        self.filter = Gtk.CustomFilter.new(self.filter_func, self.filter_model)
        self.filter_model.set_filter(self.filter)

        self.selection_model = Gtk.MultiSelection(model=self.filter_model)
        self.selection_model.connect('selection-changed', self.update_selection)

        self.set_model(self.selection_model)

    def setup(self, factory, list_item):
        list_item.set_child(EartagFileListItem(self))

    def bind(self, factory, list_item):
        child = list_item.get_child()
        file = list_item.get_item()
        child.bind_to_file(file)

    def update_selection(self, selection_model, position, n_items):
        """Updates the selected files."""
        # TODO: use get_selection_in_range to improve potential performance.
        # this is a rather naive implementation.
        #selection = self.selection_model.get_selection_in_range(position, n_items)
        selection = self.selection_model.get_selection()

        # Get list of selected items
        selected_items = []
        for i in range(selection.get_size()):
            item_no = selection.get_nth(i)
            selected_items.append(self.filter_model.get_item(item_no))

        file_count = self.filter_model.get_n_items()
        check_count = position

        self.file_manager.selected_files = selected_items

    def handle_selection_override(self, *args):
        """
        When a file is loaded and the selected files list is empty,
        the first loaded file is automatically added by the file manager
        to the list of selected files.

        Since the sidebar doesn't always listen to selection events
        (we're the primary generator of those, see function above, so
        capturing them would cause infinite loops and other problems),
        it provides a secondary event, named "selection-override", which
        is used to signify a selection event from outside the sidebar.
        """
        if self.file_manager.selected_files:
            self.selection_model.select_item(
                self.file_manager.files.find(
                    self.file_manager.selected_files[0]
                )[1], True
            )

    def filter_func(self, file, *args):
        """Custom filter for file search."""
        query = self.sidebar.search_entry.get_text()
        if not query:
            return True
        query = query.casefold()

        if query in file.title.casefold():
            return True

        if query in file.artist.casefold():
            return True

        if query in file.album.casefold():
            return True

        if query in os.path.basename(file.path).casefold():
            return True

        return False

    def sort_func(self, a, b, *args):
        """Custom sort function implementation for file sorting."""
        # Step 1. Compare album names
        a_album = GLib.utf8_casefold(a.album, -1)
        b_album = GLib.utf8_casefold(b.album, -1)
        collate = GLib.utf8_collate(a_album, b_album)

        # Step 2. Compare track numbers
        if (a.tracknumber or -1) > (b.tracknumber or -1):
            collate += 2
        elif (a.tracknumber or -1) < (b.tracknumber or -1):
            collate -= 2

        # Step 3. If the result is inconclusive, compare filenames
        if collate == 0:
            a_filename = GLib.utf8_casefold(os.path.basename(a.path), -1)
            b_filename = GLib.utf8_casefold(os.path.basename(b.path), -1)
            collate = GLib.utf8_collate(a_filename, b_filename)

        return collate

@Gtk.Template(resource_path='/app/drey/EarTag/ui/sidebar.ui')
class EartagSidebar(Gtk.Box):
    __gtype_name__ = 'EartagSidebar'

    list_stack = Gtk.Template.Child()
    list_scroll = Gtk.Template.Child()
    file_list = Gtk.Template.Child()
    no_files = Gtk.Template.Child()

    search_bar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    no_results = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

        self.search_bar.set_key_capture_widget(self)
        self.search_bar.connect_entry(self.search_entry)
        self.search_entry.connect('search-changed', self.search_changed)

    def set_file_manager(self, file_manager):
        self.file_manager = file_manager
        self.file_list.set_file_manager(self.file_manager)
        self.list_stack.set_visible_child(self.no_files)
        self.file_list.set_sidebar(self)

    def toggle_fileview(self, *args):
        """
        Shows/hides the fileview/"no files" message depending on opened files.
        """
        if self.file_manager.files.get_n_items() > 0:
            self.list_stack.set_visible_child(self.list_scroll)
        else:
            self.list_stack.set_visible_child(self.no_files)

    def search_changed(self, search_entry, *args):
        """Emitted when the search has changed."""
        self.file_list.filter.changed(Gtk.FilterChange.DIFFERENT)

        if self.file_list.filter_model.get_n_items() == 0 and \
                self.file_manager.files.get_n_items() > 0:
            self.list_stack.set_visible_child(self.no_results)
        else:
            self.toggle_fileview()

        # Scroll back to top of list
        vadjust = self.file_list.get_vadjustment()
        vadjust.set_value(vadjust.get_lower())
