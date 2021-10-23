# vim: set expandtab shiftwidth=4 softtabstop=4:
# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved. This software provided pursuant to a license 
# agreement containing restrictions on its disclosure, duplication and 
# use. For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies, including 
# partial copies, of the software or any revisions or derivations 
# thereof.
# === UCSF ChimeraX Copyright ===

from chimerax.core.tools import ToolInstance

class XMAS(ToolInstance):
    # Inheriting from ToolInstance makes us known to the ChimeraX tool 
    # manager, so we can be notified and take appropriate action when 
    # sessions are closed, saved, or restored, and we will be listed 
    # among running tools and so on.
    
    # Does this instance persist when session closes
    SESSION_ENDURING = False  
    # We do save/restore in sessions  
    SESSION_SAVE = True         
    # Let ChimeraX know about our help page
    help = "help:user/tools/tutorial.html"
                                

    def __init__(self, session, tool_name):
        # "session"   - chimerax.core.session.Session instance
        # "tool_name" - string

        # Initialize base class
        super().__init__(session, tool_name)

        # Set name displayed on title bar (defaults to tool_name)
        # Must be after the superclass init, which would override it
        self.display_name = "XMAS"

        # Create the main window for our tool. The window object will 
        # have a "ui_area" where we place the widgets composing our 
        # interface. The window isn't shown until its "manage" method 
        # is called.
        from chimerax.ui import MainToolWindow
        self.tool_window = MainToolWindow(self)

        # Method to build and show the main window
        self._build_ui()

        # Call trigger handler to take action when certain triggers fire
        self.trigger_handler()
        
        # Override the "cleanup" method to perform additional actions 
        # upon closing the main tool window
        self.tool_window.cleanup = self.cleanup

        self.pb_manager = self.session.pb_manager

        from chimerax.core.colors import Colormap
        cmap = Colormap(None, ((1, 0, 0, 1), (1, 1, 0, 1), (0, 1, 0, 1)))
        self.score_cmap = cmap.linear_range(0, 200)


    def _build_ui(self):

        # Put our widgets in the tool window
 
        from PyQt5.QtWidgets import (
            QVBoxLayout, QGridLayout, QHBoxLayout, QTreeWidget, 
            QAbstractItemView, QPushButton, QLabel, QCheckBox, QComboBox, QRadioButton, QButtonGroup, QLineEdit
            )
        from PyQt5.QtGui import QDoubleValidator
        
        outer_layout = QVBoxLayout()
        top_layout = QGridLayout()
        map_layout = QGridLayout()
        pbonds_layout = QVBoxLayout()
        buttons_layout = QHBoxLayout()
        
        # A treewidget that will contain all structural protein models 
        # open in the session
        self.model_selector = QTreeWidget()
        self.model_selector.setHeaderLabels(["Name", "ID"])
        self.model_selector.setColumnWidth(0, 200)

        # A treewidget that will contain PD evidence files that the user
        # has selected
        self.file_selector = QTreeWidget()
        self.file_selector.setHeaderLabels(["Name"])
        self.file_selector.setColumnWidth(0, 200)
        self.file_selector.setSelectionMode(QAbstractItemView.MultiSelection)

        file_button = QPushButton()
        file_button.setText("Import files")
        remove_file_button = QPushButton()
        remove_file_button.setText("Remove selected files")
        # Upon clicking the file button, a file dialog is shown, where 
        # the user can select .xlsx files
        file_button.clicked.connect(self.dialog)
        remove_file_button.clicked.connect(self.remove_files)    

        self.map_combobox = QComboBox()
        self.map_combobox.addItems(["uniform", "by distance", "by score"])
        self.map_combobox.currentIndexChanged.connect(self.radio_buttons_policy)
        radio_buttons_text = ["Gradient", "Cutoff"]
        self.radio_buttons = QButtonGroup()
        for i in range(len(radio_buttons_text)):
            text = radio_buttons_text[i]
            button = QRadioButton(text)
            self.radio_buttons.addButton(button)
            button.setEnabled(False)
            map_layout.addWidget(button, 2, i)
        radio_buttons = self.radio_buttons.buttons()
        radio_buttons[0].setChecked(True)
        radio_buttons[1].toggled.connect(self.cutoff_values_policy)
        self.cutoff_values = {}
        cutoff_labels = ["Min", "Max"]
        map_button = QPushButton()
        map_button.setText("Map crosslinks")

        map_layout.addWidget(QLabel("Mapping settings"), 0, 0, 1, 2)
        map_layout.addWidget(QLabel("Color policy:"), 1, 0)
        map_layout.addWidget(self.map_combobox, 1, 1)
        i = 2
        for label in cutoff_labels:
            qlabel = QLabel(label + ":")
            line_edit = QLineEdit()
            line_edit.setValidator(QDoubleValidator(0.0, float("inf"), 1000))
            widgets = [qlabel, line_edit]
            j = 2
            for widget in widgets:
                map_layout.addWidget(widget, i, j)
                size_policy = widget.sizePolicy()
                size_policy.setRetainSizeWhenHidden(True)
                widget.setSizePolicy(size_policy)
                widget.setVisible(False)
                j += 1
            self.cutoff_values[label] = widgets
            i += 1

        # Upon clicking the map button, the map_button_clicked method is
        # called twice, each time with different arguments
        map_button.clicked.connect(lambda: self.map_button_clicked(
            selector=self.model_selector, selector_type="model"))
        map_button.clicked.connect(lambda: self.map_button_clicked(
            selector=self.file_selector, selector_type="file"))
        
        top_layout.addWidget(QLabel("Available models"), 0, 0)
        top_layout.addWidget(QLabel("Available files"), 0, 2)
        top_layout.addWidget(self.model_selector, 1, 0, 1, 2)
        top_layout.addWidget(self.file_selector, 1, 2, 1, 2)
        top_layout.addWidget(file_button, 2, 2)
        top_layout.addWidget(remove_file_button, 2, 3)
        top_layout.addLayout(map_layout, 3, 0, 4, 2)
        top_layout.addWidget(map_button, 7, 3)

        # In this treewidget, pseudond models from .pb files are shown;
        # both models that are created with XMAS, as well as
        # models that are opened independently of XMAS.
        self.pbonds_menu = QTreeWidget()
        self.pbonds_menu.setHeaderLabels(["Name", "Model IDs"])
        self.pbonds_menu.setColumnWidth(0, 300)
        # When a pseudobond model is (de)selected in the menu, it should
        # also be (de)selected in the ChimeraX session. Call
        # "check_signal" method to arrange this        
        self.pbonds_menu.itemChanged.connect(self.check_signal)

        pbonds_layout.addWidget(QLabel("Crosslink models"))
        pbonds_layout.addWidget(self.pbonds_menu)

        subset_button = QPushButton()
        subset_button.setText("Export subsets")
        shortest_button = QPushButton()
        shortest_button.setText("Find shortest")
        distance_button = QPushButton()
        distance_button.setText("Plot distances")
        overlap_button = QPushButton()
        overlap_button.setText("Plot overlap")
        buttons = [subset_button, shortest_button, distance_button, overlap_button]
        functions = [self.show_subset_dialog, self.find_shortest, self.create_distance_plot, self.create_venn]

        # Upon clicking the subset button, a dialog is opened where the 
        # user can select the parameters for the data subset required
        for i in range(len(buttons)):
            button = buttons[i]
            buttons_layout.addWidget(button)
            function = functions[i]
            button.clicked.connect(function)

        outer_layout.addLayout(top_layout)
        outer_layout.addLayout(pbonds_layout)
        outer_layout.addLayout(buttons_layout)

        # Set the layout as the contents of our window
        self.tool_window.ui_area.setLayout(outer_layout)

        # Show the tool in the ChimeraX main window. Given its 
        # relatively large size, the tool is not shown on the 
        # user-preferred side of the window, which would have been 
        # arranged by 'self.tool_window.manage("side")'
        self.tool_window.manage(None)

        # Create an empty dictionary where pb models made with Crosslink
        # Mapper will be stored
        self.created_models = {}

        # Add models open in session to the window with the "add_models"
        # method 
        self.add_models(self.session.models)

    
    def cutoff_values_policy(self, checked):

        key = list(self.cutoff_values.keys())[0]
        widget = self.cutoff_values[key][0]
        visible = widget.isVisible()

        if (visible and not checked):
            set_visible = False
        elif (not visible and checked):
            set_visible = True
        else:
            return

        for key in self.cutoff_values:
            widgets = self.cutoff_values[key]
            for widget in widgets:
                widget.setVisible(set_visible)


    def radio_buttons_policy(self, index):
        
        radio_buttons = self.radio_buttons.buttons()
        radio_gradient = radio_buttons[0]
        enabled = radio_gradient.isEnabled()

        if (enabled and index == 0):
            enable = False
            self.cutoff_values_policy(False)
        elif (not enabled and index != 0):
            enable = True
            if radio_buttons[1].isChecked():
                self.cutoff_values_policy(True)
        else:
            return
    
        for button in radio_buttons:
            button.setEnabled(enable) 


    def remove_files(self):

        from PyQt5.QtWidgets import QTreeWidgetItemIterator

        iterator = QTreeWidgetItemIterator(self.file_selector, QTreeWidgetItemIterator.Selected)

        if not iterator.value():
            return

        remove = []

        while iterator.value():
            item = iterator.value()
            remove.append(item)
            del self.evidence_files[item.text(0)]      
            iterator += 1

        root = self.file_selector.invisibleRootItem()      

        for item in remove:
            root.removeChild(item) 


    def find_shortest(self):

        from PyQt5.QtWidgets import QTreeWidgetItemIterator
        from PyQt5.QtCore import Qt

        iterator = QTreeWidgetItemIterator(
            self.pbonds_menu, QTreeWidgetItemIterator.Checked)

        if not iterator.value():
            print("Please select pseudobonds")
            return

        models = self.session.models

        while iterator.value():
            item = iterator.value()
            model = item.model
            pbs = model.pseudobonds
            pbs_dict = {}
            name = model.name.replace(".pb", "")
            new_name = name + "_shortest.pb"

            for pb in pbs:
                peptide_pairs = pb.peptide_pairs
                for pair in peptide_pairs:
                    if not pair in pbs_dict:
                        pbs_dict[pair] = []
                    pbs_dict[pair].append(pb)
            
            group = self.pb_manager.get_group(new_name)
            group.color = [255, 255, 0, 255]
            group.radius = 0.5

            shortest_pbs = []

            for pair in pbs_dict:
                minimum = float("inf")
                pbs = pbs_dict[pair]              
                for pb in pbs:
                    length = pb.length
                    if length < minimum:
                        minimum = length 
                for pb in pbs:
                    if pb.length > minimum:
                        continue
                    shortest_pbs.append(pb)

            pbs_atoms_dict = self.pbs_atoms(shortest_pbs, find_shortest=True)
            
            for atoms in list(pbs_atoms_dict.keys()):
                group.new_pseudobond(atoms[0], atoms[1])
            
            models.add([group])

            group_item = self.pbonds_menu.findItems(
                    new_name, Qt.MatchExactly, column=0)[0]
            group_item.setText(1, item.text(1))

            iterator += 1


    def create_venn(self):

        import matplotlib.pyplot as plt
        
        pbs_dict = self.get_pseudobonds_dict(distance=False)

        number_of_groups = len(pbs_dict)

        if (number_of_groups > 2 and number_of_groups < 8):
            from matplotlib_venn import venn3
            function = venn3
        elif number_of_groups == 2:
            from matplotlib_venn import venn2
            function = venn2
        else:
            return

        sets = []

        for pb_group in pbs_dict:
            pbs = pbs_dict[pb_group]
            sets.append(set(pbs))

        function(sets, tuple(pbs_dict.keys()))
        plt.show()


    def create_distance_plot(self):

        import seaborn as sns
        import matplotlib.pyplot as plt

        pbs_dict = self.get_pseudobonds_dict()   

        models = list(pbs_dict.keys())
        distances = list(pbs_dict.values())       

        sns.set(style="whitegrid")
        ax = sns.boxenplot(data=distances, orient="h")
        ax = sns.stripplot(data=distances, orient="h", size = 4, color = "gray")
        plt.xlabel("Distance (Å)")
        yticks = plt.yticks(plt.yticks()[0], models)
        plt.tight_layout()
        plt.show()


    def get_pseudobonds_dict(self, distance=True):
        from chimerax.atomic.pbgroup import selected_pseudobonds

        selected_pbs = selected_pseudobonds(self.session)
        by_group = selected_pbs.by_group
        pbs_dict = {}

        for group in by_group:
            name = group[0].name
            if not name.endswith(".pb"):
                continue
            key = name.replace(".pb", "")
            pbs = group[1]
            if distance:
                value = [pb.length for pb in pbs]
            else:
                value = [pb.string() for pb in pbs]
            pbs_dict[key] = value

        return pbs_dict
    
    def dialog(self):

        # The user has clicked the file button: with this dialog, 
        # evidence files can be selected

        from PyQt5.QtWidgets import QFileDialog, QTreeWidgetItem
        from PyQt5.QtCore import Qt

        file_dialog = QFileDialog()
        # Set file mode to existing files to enable selection of multiple files
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        selected_files, _ = QFileDialog.getOpenFileNames(None, "Select evidence files", "", "Excel (*.xlsx)")

        # Create a dictionary containing the evidence files to avoid 
        # showing the same file multiple times
        if not hasattr(self, "evidence_files"):
            self.evidence_files = {}
        for selected_file in selected_files:
            if selected_file in self.evidence_files.values():
                selected_files.remove(selected_file)
        number_of_files = len(selected_files)
        # Store the number of files in the treewidget to give each file 
        # a proper ID
        if not hasattr(self, "number_of_items"):
            self.number_of_items = 0
        i = 0
        # Files get a unique letter sequence as ID, which is created by 
        # the "file_id_generator" method, and are added to the 
        # treewidget
        for ID in self.file_id_generator(
            self.number_of_items, self.number_of_items + number_of_files):
            path_to_file = selected_files[i]
            short_name = self.get_short_filename(path_to_file)
            item = QTreeWidgetItem(self.file_selector)
            item.setText(0, short_name)
            item.setCheckState(0, Qt.Checked)
            i += 1
            self.evidence_files[short_name] = path_to_file
            self.number_of_items += 1


    def file_id_generator(self, start, end):

        # Creates file IDs for user-selected evidence files. The start 
        # index is specified, so that the generator does not start over 
        # every time new files are selected. The end index is pecified, 
        # so that the number of IDs created corresponds to the number 
        # of newly added files.

        import string
        import itertools

        for i in itertools.count(1):
            for p in itertools.product(string.ascii_uppercase, repeat=i):
                start -= 1
                if (end > 0 and start < 0):
                    yield "".join(p)
                    end -= 1
                elif (end > 0 and start > -1):
                    end -= 1
                else:
                    break
            if end < 1:
                break


    def get_short_filename(self, path_to_file):        

        # Method to obtain a short name to represent a file or model in
        # the tool

        import re

        short_name = re.search("[^/]+\Z", path_to_file).group(0)

        return short_name


    def map_button_clicked(self, selector, selector_type):

        # The user has clicked the map button: the selected models and 
        # files are extracted from their respective selector treewidgets

        from PyQt5.QtWidgets import QTreeWidgetItemIterator

        iterator = QTreeWidgetItemIterator(
            selector, QTreeWidgetItemIterator.Checked)
        # If no models/files have been selected, print a message
        if not iterator.value():
            print("Please check one or more %ss" % selector_type)
            self.missing_data = True
        else:
            checked_items = []
            while iterator.value():
                item = iterator.value()
                if selector_type == "model":
                    ID = item.text(1)
                elif selector_type == "file":
                    ID = item.text(0)
                iterator += 1
                checked_items.append(ID)
            if selector_type == "model":
                self.checked_models = checked_items
                self.missing_data = False
            elif selector_type == "file":
                number_of_checked_files = len(checked_items)
                checked_files = [None]*number_of_checked_files
                for i in range(number_of_checked_files):
                    checked_files[i] = self.evidence_files[checked_items[i]]
                # If no models have been selected, mapping should not
                # be performed. Therefore, "missing_data" has to be
                # False. Mapping is performed by a call to the
                # "map_crosslinks" method
                if not self.missing_data:
                    self.map_crosslinks(
                        checked_items, self.checked_models, checked_files)


    def map_crosslinks(self, checked_items, checked_models, checked_files):
        
        # The user has selected one or multiple models and evidence
        # files, and clicked the map button: map crosslinked peptides

        import pandas as pd
        from PyQt5.QtCore import Qt

        # Each checked file is mapped to all checked models
        for j in range(len(checked_files)):

            evidence_file = checked_files[j]

            # Display bold log message to signify which file is being
            # mapped
            self.session.logger.info(
                "<br><b>Peptide pair mapping of PD output file: %s</b>" 
                % evidence_file, is_html=True)
            
            # Read the file and extract the peptide pairs from it
            dataframe = pd.read_excel(evidence_file)
            
            input_peptides_A = dataframe["Sequence A"].tolist()
            input_peptides_B = dataframe["Sequence B"].tolist()
            xlinkx_scores = dataframe["Max. XlinkX Score"].tolist()

            input_pairs = []
            # Keep track of peptide pairs with lacking sequence
            # information
            sequence_info_lacking = 0

            # Peptides within the peptide pairs are sorted, to be able
            # to remove inversely identical peptide pairs
            for i in range(len(dataframe.index)):
                peptide_A = input_peptides_A[i]
                peptide_B = input_peptides_B[i]
                if (type(peptide_A) != str or type(peptide_B) != str):
                    sequence_info_lacking += 1
                    continue
                input_pairs.append([sorted([peptide_A, peptide_B]), xlinkx_scores[i]])
                
            # Print a message when one or multiple peptide pairs lack
            # sequence information
            if sequence_info_lacking == 1:
                print("1 peptide pair is disregarded due to lacking "
                    "sequence information")
            elif sequence_info_lacking >= 1:
                print("%s peptide pairs are disregarded due to"
                    % str(sequence_info_lacking),         
                    "lacking sequence information")

            input_pairs_deduplicated = list(self.deduplicate(input_pairs))

            # Print a message stating how many peptide pairs were unique
            number_of_deduplicated = len(input_pairs_deduplicated)
            print("Unique peptide pairs: %s out of %s" 
                % (number_of_deduplicated, len(input_pairs)))

            # Store all peptide pairs in list of lists
            # Each peptide is stored as a Peptide object, that contains
            # the peptide sequence, the position of the crosslinked
            # residue, and any alignments on the model(s).

            peptide_pairs = [None] * number_of_deduplicated

            for i in range(number_of_deduplicated):
                input_pair = input_pairs_deduplicated[i]
                peptides = input_pair[0]
                xlinkx_score = input_pair[1]
                peptide_pairs[i] = PeptidePair(peptides, xlinkx_score)

            # Now we align all peptides to the sequences of all chains
            # open in the ChimeraX session
            #
            # The peptide sequences are compared to the sequences
            # string of all chains. The index of a crosslinked residue
            # on the sequence string is always different than its
            # "number" attribute of the corresponding Residue object in
            # ChimeraX, since numbering Residue objects commences with
            # the number 1 or higher, instead of 0. To ensure that the
            # right residue number is used in the .pb file, the first
            # residue number of each chain is stored, which is then
            # added to the index found on the sequence string.
            # Furthermore, some residues are present in the sequence
            # string, but their Residue objects are not shown in the
            # Chimerax structure. These Residue objects are of type
            # NoneType, and ChimeraX does not enable creating
            # pseudobonds between NoneType residues. To prevent adding
            # these crosslinks to the .pb file, the positions of all
            # NoneType residues is also stored.

            for model in self.session.models:
                model_id = model.id_string
                if model_id not in checked_models:
                    continue
                for chain in model.chains:
                    # Keep track of the number of NoneType residues at
                    # the start of the sequence. These will influence
                    # the first residue number         
                    preceding_nonetypes = 0
                    first_residue_number_found = False
                    chain_sequence = chain.characters
                    nonetype_positions = []
                    residues = chain.residues
                    for i in range(len(residues)):
                        residue = residues[i]
                        if (residue is None 
                                and not first_residue_number_found):
                            preceding_nonetypes += 1
                            nonetype_positions.append(i)
                        elif (residue is None 
                                and first_residue_number_found):
                            nonetype_positions.append(i)
                        elif (residue is not None 
                                and not first_residue_number_found):
                            first_residue_number = (
                                residue.number - preceding_nonetypes)
                            first_residue_number_found = True
                    # Loop all peptide sequences over the chain to find
                    # perfect alignments
                    for peptide_pair in peptide_pairs:
                        for peptide in peptide_pair.peptides:
                            peptide_sequence = peptide.sequence
                            peptide_length = len(peptide_sequence)
                            for start in range(
                                    len(chain_sequence) - peptide_length + 1):
                                end = start + peptide_length
                                # If the crosslinked residue is not
                                # present in the structure, the
                                # pseudobond cannot be mapped, and
                                # therefore we will disregard this
                                # alignment                                
                                crosslink_position = (
                                    start + peptide.crosslink_position)
                                if crosslink_position in nonetype_positions:
                                    continue
                                if (chain_sequence[start:end] 
                                        == peptide_sequence):
                                    alignment = Alignment(
                                        start, end, first_residue_number, 
                                        crosslink_position, model_id,
                                        chain)
                                    peptide.alignments.append(alignment)                    

            # Continue with creating all valid pseudobonds for all
            # peptide pairs and store them in a list. If both peptides
            # of a pair are aligned on the same chain, these alignments
            # are checked for overlap. Make separate lists for peptide
            # pairs with non-overlapping peptides and those with
            # overlapping peptides. Overlapping peptides can be
            # categorized as nonself-links and selflinks

            pbonds_unfiltered = []
            pbonds = []
            pbonds_overlapping = []
            pbonds_overlapping_selflinks = []
            pbonds_overlap_associated = []

            # The number of perfectly aligned peptide pairs is counted
            number_of_aligned_pairs = 0

            for peptide_pair in peptide_pairs:
            # First select the peptide pairs for which both peptides
            # have alignments. Each possible pseudobond is stored as a
            # PrePseudobond object  
                pair = peptide_pair.peptides
                if (len(pair[0].alignments) > 0 
                        and len(pair[1].alignments) > 0):
                    number_of_aligned_pairs += 1   
                    pbonds_unfiltered = [
                        PrePseudobond(a, b, peptide_pair) for a in pair[0].alignments 
                        for b in pair[1].alignments
                        ]

                if len(pbonds_unfiltered) == 0:
                    continue      

                # Check whether the peptide has pseudobonds for overlapping peptides
                peptide_pair.has_overlapping = False       
                for pb in pbonds_unfiltered:
                    if pb.is_overlapping:
                        peptide_pair.has_overlapping = True
                        break
             
                # Then write pseudobonds in their appropriate
                # lists.     
                for pb in pbonds_unfiltered:
                    if (not pb.is_overlapping and not pb.is_selflink):
                        pbonds.append(pb)
                        if peptide_pair.has_overlapping:
                            pbonds_overlap_associated.append(pb)
                    elif (pb.is_overlapping and not pb.is_selflink):
                        pbonds_overlapping.append(pb)
                    elif pb.is_selflink:
                        pbonds_overlapping_selflinks.append(pb)   
            
            # Print a log message stating how many peptide pairs for
            # which perfect alignments have been found
            print("Unique peptide pairs with pseudobonds: %s" 
                % number_of_aligned_pairs)    
    
            if len(pbonds) > 0:
                # Create a code for the model with all model IDs and
                # the evidence file ID that was used
                model_ids = ",".join([
                    str(model_id) for model_id in checked_models
                    ])
                pb_file_code = model_ids
                pb_file_path = evidence_file.replace(".xlsx", "_%s.pb"
                    % pb_file_code)
                print("Pseudobonds opened from %s" % pb_file_path)
                # Create a new pseudobonds model
                created_model = self.create_pseudobonds_model(pbonds, pb_file_path)
                # Store the model and its code in the "created_models"
                # dictionary
                if created_model not in self.created_models.keys():
                    self.created_models[created_model] = pb_file_code
                # Show the code of this file in the pbonds menu                
                item = self.pbonds_menu.findItems(
                    created_model, Qt.MatchExactly, column=0)[0]
                item.setText(1, pb_file_code)

            # Write .pb files for peptide pairs with overlapping
            # peptides:    

            # Self-links and non-self-links should be stored in
            # separate files, since ChimeraX cannot open self-links

            no_overlapping_nonself = 0
            no_overlapping_self = 0   

            if len(pbonds_overlapping) > 0:
                nonself_path = pb_file_path.replace(
                    ".pb", "_overlapping.pb")
                no_overlapping_nonself = self.write_file(nonself_path, pbonds_overlapping, file_type=".pb overlapping")
            if len(pbonds_overlapping_selflinks) > 0:
                self_path = pb_file_path.replace(
                    ".pb", "_overlapping_selflinks.pb")
                no_overlapping_self = self.write_file(self_path, pbonds_overlapping_selflinks, file_type=".pb overlapping")
            if len(pbonds_overlap_associated) > 0:
                associated_path = pb_file_path.replace(
                    ".pb", "_overlap_associated.pb")
                no_overlap_associated = self.write_file(associated_path, pbonds_overlap_associated, file_type=".pb overlapping")
                    
            no_overlapping = (no_overlapping_nonself
                + no_overlapping_self)

            # Print a log message stating how many pseudobonds were
            # not mapped due to overlapping peptides
            if no_overlapping == 1:
                print("1 pseudobond was not mapped due to overlapping "
                    "peptides.")
            elif no_overlapping > 1:
                print("%s pseudobonds were not mapped due to overlapping"
                    % no_overlapping, "peptides." )

            # Tell the user in which files the pseudobonds from
            # overlapping peptides can be found
            if (len(pbonds_overlapping) > 0 
                    and len(pbonds_overlapping_selflinks) == 0):
                print("These pseudobonds were stored in %s."
                    % nonself_path)
            elif (len(pbonds_overlapping) > 0 
                    and len(pbonds_overlapping_selflinks) > 0):
                print("%s of these pseudobonds were self-links.\n"
                    % no_overlapping_self
                    + "Self-links were stored in %s.\n" 
                    % self_path
                    + "The remaining %s pseudobonds were stored in %s."
                    % (no_overlapping_nonself, nonself_path))
            elif (len(pbonds_overlapping) == 0
                    and len(pbonds_overlapping_selflinks) > 0):
                print("All of these pseudobonds were self-links, "
                    "and stored in %s." % self_path)

            if len(pbonds_overlap_associated) > 0:
                associated_path = pb_file_path.replace(
                    ".pb", "_overlap_associated.pb")
                self.write_file(associated_path, pbonds_overlap_associated, file_type=".pb overlapping")
                print("%s pseudobonds from non-overlapping peptides belonged to a peptide pair that did yield overlapping peptides for one or more other pseudobonds. These overlap-associated pseudobonds were stored in %s." % (no_overlap_associated, associated_path))

                   
    def create_pseudobonds_model(self, pbonds, file_path):

        from PyQt5.QtCore import Qt 
        from chimerax.color_key.model import get_model

        color_policy = self.map_combobox.currentText().replace("by ", "")
        if color_policy != "uniform":
            uniform = False
            radio_button = self.radio_buttons.checkedButton().text()
            file_path = file_path.replace(".pb", "_" + color_policy + "_" + radio_button.lower() + ".pb")
        else:
            uniform = True
            radio_button = None

        name = self.get_short_filename(file_path)
        group = self.pb_manager.get_group(name)
        if group.num_pseudobonds > 0:
            group.clear()
        self.session.models.add([group])
        group.radius = 0.5
        group.color = [255, 255, 0, 255]
        group.dashes = 8

        pbs_atoms_dict = self.pbs_atoms(pbonds)
            
        for atoms in list(pbs_atoms_dict.keys()):
            new_pb = group.new_pseudobond(atoms[0], atoms[1])
            new_pb.line = self.create_pb_line(new_pb)
            peptide_pairs = new_pb.peptide_pairs = pbs_atoms_dict[atoms]
            max_score = 0
            for peptide_pair in peptide_pairs:
                score = peptide_pair.xlinkx_score
                if score <= max_score:
                    continue
                max_score = score
            new_pb.xlinkx_score = max_score
            if color_policy == "score":
                color = self.get_color(color_policy, new_pb.xlinkx_score, radio_button, self.score_cmap)
                new_pb.color = color

        if radio_button == "Gradient":
            group.dashes = 0
            if color_policy == "distance":
                pbs = group.pseudobonds
                minimum, maximum = self.extreme_pseudobond_distances(pbs)
                distances = [minimum, maximum]
            else:
                distances = None
            m = ColorScore(self.session, distances, name)
            self.session.models.add([m], root_model=True)

        if color_policy == "distance":
            if radio_button == "Gradient":
                cmap = m.cmap
            else:
                cmap = None
            for pb in group.pseudobonds:
                pb.color = self.get_color(color_policy, pb.length, radio_button, cmap)

        if uniform:
            coloring = False
        else:
            coloring = True
        self.write_file(file_path, group, file_type=".pb", coloring=coloring)


        return name


    def create_pb_line(self, pb):

        atom1, atom2 = pb.atoms
        atom1_string = atom1.string(style="command line", omit_structure=False)
        atom2_string = atom2.string(style="command line", omit_structure=False)
        atoms_sorted = sorted([atom1_string, atom2_string])
        pb_line = atoms_sorted[0] + " " + atoms_sorted[1]

        return pb_line

    
    def pbs_atoms(self, pbs, find_shortest=False):
        
        length = len(pbs)
        atom_dict = {}    
        for i in range(length):
            pb = pbs[i]
            if not find_shortest:
                atom1, atom2 = pb.atom1, pb.atom2
            else:
                atom1, atom2 = pb.atoms
            atoms = sorted([atom1, atom2])
            atoms = tuple(atoms)
            if atoms not in atom_dict.keys():
                atom_dict[atoms] = []
            if find_shortest:
                continue
            atom_dict[atoms].append(pb.peptide_pair)

        return atom_dict


    def get_color(self, color_policy, value, radio_button, cmap):

        if (value > 200 and color_policy == "score" and radio_button == "Gradient"):
                value = 200  

        if radio_button == "Gradient":
            rgba8_list = cmap.interpolated_rgba8([value])
            rgba8 = rgba8_list[0]
        elif radio_button == "Cutoff":
            minimum_value = self.cutoff_values["Min"][1].text()
            if minimum_value == "":
                minimum = 0
            else:
                minimum = float(minimum_value)
            maximum_value = self.cutoff_values["Max"][1].text()
            if maximum_value == "":
                maximum = float("inf")
            else:
                maximum = float(maximum_value)
            
            if (value < minimum or value > maximum):
                rgba8 = [255, 0, 0, 255]
            else:
                rgba8 = [255, 255, 0, 255]

        return rgba8
        

    def deduplicate(self, lst):

        # Method that removes duplicate items from a list

        lst.sort()
        last = object()
        for item in lst:
            if item == last:
                continue
            yield item
            last = item


    def write_file(self, file_path, group, file_type=".pb", coloring=False):

        # Write a file

        if file_type == ".pb":
            pbs = group.pseudobonds
            radius = 0.5
            dashes = 8
            standard_color = " #ffff00"
            all_standard = True
        else:
            pbs = group

        number_of_pbs = len(pbs)
        lines = [None] * number_of_pbs
        if (file_type == ".pb" or file_type == ".pb overlapping"):
            for i in range(number_of_pbs):
                pb = pbs[i]
                if (coloring and not ".pb overlapping"):
                    color = " #%02x%02x%02x%02x" % tuple(pb.color)
                    if color != standard_color:
                        all_standard = False
                else:
                    color = ""
                lines[i] = "%s%s" % (pb.line, color)
            if coloring and all_standard:
                for i in range(number_of_pbs):
                    lines[i] = lines[i].replace(standard_color, "")           
        elif file_type == "export":
            for i in range(number_of_pbs):
                lines[i] = pbs[i]

        lines_deduplicated = list(self.deduplicate(lines))

        if file_type == ".pb":
            if group.radius != 0.5:
                radius_line = "; radius = %s" % group.radius
                lines_deduplicated.insert(0, radius_line)
            if group.dashes != dashes:
                dashes_line = "; dashes = %s" % group.dashes
                lines_deduplicated.insert(0, dashes_line)

        created_file = open(file_path, "w")
        for line in lines_deduplicated:
            created_file.write(line + "\n")
        created_file.close()

        return len(lines_deduplicated)


    def check_signal(self, item, column):

        # (De)select models depending on the item (de)selected in the
        # pbonds menu

        from PyQt5.QtCore import Qt

        for model in self.session.models:
            if (model.name == item.text(column) 
                    and item.checkState(column) == Qt.Checked):
                model.selected = True
            elif (model.name == item.text(column)
                    and item.checkState(column) == Qt.Unchecked):
                model.selected = False
                

    def show_subset_dialog(self):

        # Through this dialog, the user can export a subset of the
        # models selected in the pbonds menu

        pseudobonds, models = self.get_pseudobonds_models()

        if len(pseudobonds) == 0:
            print("Please select pseudobonds")
            return

        from PyQt5.QtWidgets import (QGridLayout, QDialog, QTreeWidget, QTreeWidgetItem, QListWidget, 
            QListWidgetItem, QPushButton, QHBoxLayout, QComboBox, QCheckBox, QLabel)
        from PyQt5.QtCore import Qt

        layout = QGridLayout()

        self.subset_dialog = QDialog()
        self.subset_dialog.setWindowTitle("Export subset of the selected pseudobonds")

        self.dialog_model_selector = QTreeWidget()
        self.dialog_model_selector.setHeaderLabels(["Name", "ID"])

        for model in models:
            item = QTreeWidgetItem(self.dialog_model_selector)
            item.setText(0, model.name)
            item.setText(1, model.id_string)
            item.setCheckState(0, Qt.Checked)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.model = model

        self.dialog_model_selector.sortItems(1, Qt.AscendingOrder)

        # Menu to select whether only intralinks, only interlinks, or
        # both need to be exported
        self.link_selector = QListWidget()
        link_types = ["Intralinks", "Interlinks"]
        for link_type in link_types:
            item = QListWidgetItem(self.link_selector)
            item.setText(link_type)
            item.setCheckState(Qt.Checked)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        if len(models) == 1:
            item = self.link_selector.findItems("Interlinks", Qt.MatchExactly)[0]
            item.setFlags(Qt.NoItemFlags)
        
        pbs = self.get_pseudobonds()
        _, maximum_distance = self.extreme_pseudobond_distances(pbs)
        self.distance_slider = Slider("distance", True, maximum_distance, pbs)
        make_score_slider = True
        for pb in pbs:
            if not hasattr(pb, "xlinkx_score"):
                make_score_slider = False
                score_slider = Slider("score", False)
                break
        if make_score_slider:
            maximum_score = self.get_maximum_score(pbs)
            score_slider = Slider("score", True, maximum_score, pbs)

        self.overlap_number = QComboBox()
        number_of_groups = self.get_pseudobond_groups(pseudobonds)
        overlap_list = [str(i) for i in range(1, number_of_groups + 1)]
        self.overlap_number.addItems(overlap_list)
        overlap_string = "out of %s pseudobond models" % str(number_of_groups)

        overlap_layout = QHBoxLayout()
        overlap_layout.addWidget(self.overlap_number)
        overlap_layout.addWidget(QLabel(overlap_string))
        
        export_button = QPushButton("Export")

        self.checkbox_pb = QCheckBox(".pb")
        self.checkbox_pb.setChecked(True)
        self.checkbox_disvis = QCheckBox("DisVis")
        self.checkbox_haddock = QCheckBox("HADDOCK")
        checkboxes = {"Pb":self.checkbox_pb, "DisVis":self.checkbox_disvis, "HADDOCK":self.checkbox_haddock}
        
        checkbox_layout = QHBoxLayout()
        for checkbox in checkboxes:
            current = checkboxes[checkbox]
            # Until this can be implemented:
            if current.text() == "HADDOCK":
                break
            checkbox_layout.addWidget(current)

        layout.addWidget(QLabel("Models:"), 0, 0)
        layout.addWidget(self.dialog_model_selector, 1, 0)
        layout.addWidget(QLabel("Links:"), 0, 1)
        layout.addWidget(self.link_selector, 1, 1)
        layout.addWidget(QLabel(""), 2, 0)
        layout.addLayout(self.distance_slider.layout, 3, 0, 2, 2)
        layout.addLayout(score_slider.layout, 5, 0, 2, 2)
        layout.addWidget(QLabel(""), 7, 0)
        layout.addWidget(QLabel("Present in at least:"), 8, 0)
        layout.addLayout(overlap_layout, 9, 0)
        layout.addWidget(QLabel(""), 10, 0)
        layout.addLayout(checkbox_layout, 11, 0)       
        layout.addWidget(export_button, 11, 1)

        self.subset_dialog.setLayout(layout)
        
        export_button.clicked.connect(lambda: self.export_subset(pseudobonds, checkboxes))

        self.subset_dialog.show()
        self.subset_dialog.rejected.connect(lambda: self.display_all(pseudobonds))

    
    def get_maximum_score(self, pbs):

        maximum = 0

        for pb in pbs:
            if pb.xlinkx_score <= maximum:
                continue
            maximum = pb.xlinkx_score

        return int(maximum) + 1


    def extreme_pseudobond_distances(self, pbs):

        minimum = float("inf")
        maximum = 0

        for pb in pbs:
            length = pb.length
            if length < minimum:
                minimum = length
            if length > maximum:
                maximum = length

        minimum = int(minimum)
        maximum = int(maximum) + 1

        return minimum, maximum


    def get_pseudobonds(self):

        from chimerax.atomic.pbgroup import selected_pseudobonds

        all_selected_pbs = selected_pseudobonds(self.session)
        target_pbs = []

        for pb in all_selected_pbs:
            if pb.group.name.endswith(".pb"):
                target_pbs.append(pb)

        return target_pbs


    def get_pseudobond_groups(self, pseudobonds):

        pb_groups = set()

        for pb in pseudobonds:
            pb_groups.add(pb.group)

        return len(pb_groups)      


    def get_pseudobonds_models(self):

        # For each selected pseudobond, the IDs of the models that it
        # is connected to are added to a set. This is then converted to
        # a list, containing the IDs of all models that the selected
        # pseudobonds are connected to.

        from chimerax.atomic.pbgroup import PseudobondGroup
        from chimerax.atomic.structure import Structure

        target_pbs = self.get_pseudobonds()
        pb_strings = set()
        models = set()
        pbs = []

        for model in self.session.models:
            if (isinstance(model, PseudobondGroup) 
                    or not isinstance(model, Structure)):
                continue
            for pb in target_pbs:
                pb_strings.add(pb.string())
                atom1, atom2 = pb.atoms
                if (atom1 in model.atoms or atom2 in model.atoms):
                    # Don't create a new set for every model
                    if not hasattr(pb, "models"):
                        pb.models = set()
                    pb.models.add(model)
                    models.add(model)

        for pb in target_pbs:
            if pb.string() in pb_strings:
                pbs.append(pb)

        return pbs, list(models)


    def export_subset(self, pseudobonds, checkboxes):

        from PyQt5.QtWidgets import QTreeWidgetItemIterator, QFileDialog
        from PyQt5.QtCore import Qt

        checked = True

        model_iterator = QTreeWidgetItemIterator(self.dialog_model_selector, QTreeWidgetItemIterator.Checked)
        if not model_iterator.value():
            print("Please check one or more models")
            checked = False

        links = []
        for i in range(self.link_selector.count()):
            item = self.link_selector.item(i)
            if item.checkState() == Qt.Unchecked:
                continue
            links.append(item.text())
        number_of_links = len(links)
        if number_of_links == 0:
            print("Please check one or more links")
            checked = False

        if not checked:
            return

        models = []
        valid_pseudobonds = []
        
        while model_iterator.value():
            item = model_iterator.value()
            models.append(item.model)
            model_iterator += 1

        minimum_distance = int(self.distance_slider.setter_min.text())
        maximum_distance = int(self.distance_slider.setter_max.text())

        def get_pass(pb):

            minimum_score = int(self.score_slider.setter_min.text())
            maximum_score = int(self.score_slider.setter_max.text())
            score = pb.xlinkx_score

            if (score < minimum_score or score > maximum_score):
                return False

            return True

        def give_pass(pb):

            return True


        if self.score_slider.enabled:
            function = get_pass
        else:
            function = give_pass

        for pb in pseudobonds:
            in_models = True
            for model in pb.models:
                if model not in models:
                    in_models = False
                    break
            if not in_models:
                continue
            length = pb.length
            if (length < minimum_distance or length > maximum_distance):
                continue
            pass_pb = function(pb)
            if not pass_pb:
                continue
            if number_of_links == 1:
                link = links[0]
                number_of_models = len(pb.models)
                if (link == "Intralinks" and number_of_models != 1):
                    continue
                elif (link == "Interlinks" and number_of_models != 2):
                    continue            
            valid_pseudobonds.append(pb)

        number_for_overlap = int(self.overlap_number.currentText())
        if number_for_overlap > 1:
            pb_strings = [pb.string() for pb in valid_pseudobonds]
            remove = []
            for string in pb_strings:
                if pb_strings.count(string) >= number_for_overlap:
                    continue
                remove.append(string)
            for string in remove:
                for pb in valid_pseudobonds:
                    if pb.string() != string:
                        continue
                    valid_pseudobonds.remove(pb)
                    break

        if len(valid_pseudobonds) == 0:
            print("No pseudobonds match the criteria")
            return

        if checkboxes["Pb"].isChecked():
            pb_lines = []
            for pb in valid_pseudobonds:
                if hasattr(pb, "line"):
                    pb_line = pb.line
                else:
                    pb_line = self.create_pb_line(pb)
                pb_lines.append(pb_line)
            if not checkboxes["DisVis"].isChecked():
                self.save_subset("Save pseudobonds", "*.pb", [pb_lines])
                self.subset_dialog.close()
            else:
                self.show_disvis_dialog(models, valid_pseudobonds, pb_lines)

        elif (not checkboxes["Pb"].isChecked() and checkboxes["DisVis"].isChecked()):
            self.show_disvis_dialog(models, valid_pseudobonds)


    def display_all(self, pseudobonds):

        for pb in pseudobonds:
            pb.display = True


    def save_subset(self, title, extension, lists):

        from PyQt5.QtWidgets import QFileDialog
        import re

        file_path, _ = QFileDialog.getSaveFileName(self.subset_dialog, title, "", extension)

        if file_path == "":
            return

        file_path = re.search("[^.]+", file_path).group(0)
        extensions = [".pb", ".txt"]

        for i in range(len(lists)):
            lst = lists[i]
            if lst is None:
                continue
            current_path = file_path + extensions[i]
            self.write_file(current_path, lst, file_type="export")


    def show_disvis_dialog(self, models, pseudobonds, pb_lines=None):

        from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QButtonGroup, QRadioButton, QLineEdit, QDialogButtonBox
        from PyQt5.QtGui import QDoubleValidator

        self.disvis_dialog = QDialog(self.subset_dialog)
        self.disvis_dialog.setWindowTitle("Create DisVis input file")

        models_layout = QHBoxLayout()
        fix_layout = QVBoxLayout()
        scanning_layout = QVBoxLayout()
        distances_layout = QGridLayout()
        outer_layout = QVBoxLayout()

        chain_selection = {"Fix chain:":fix_layout, "Scanning chain:":scanning_layout}
        groups = [None] * len(chain_selection)

        i = 0  
        for chain in chain_selection:
            layout = chain_selection[chain]
            layout.addWidget(QLabel(chain))
            group = QButtonGroup(self.disvis_dialog)
            for model in models:
                model_string = model.name + " (" + model.id_string + ")"
                button = QRadioButton(model_string)
                button.model = model
                group.addButton(button)
                layout.addWidget(button)
            group.buttons()[0].toggle()   
            groups[i] = group            
            i += 1 
            models_layout.addLayout(layout)
        
        distance_options = ["Minimum", "Maximum"]
        number_of_options = len(distance_options)
        line_edits = [None] * number_of_options
        for i in range(number_of_options):
            distance = distance_options[i]
            label = QLabel(distance + " distance:")
            distances_layout.addWidget(label, i, 0)
            line_edit = QLineEdit()
            line_edit.setValidator(QDoubleValidator(0.0, float("inf"), 1000))
            line_edits[i] = line_edit
            distances_layout.addWidget(line_edit, i, 1)

        def get_parameters():

            chains_keys = ["Fixed", "Scanning"]
            chains = {}
            for i in range(len(groups)):
                group = groups[i]
                model = group.checkedButton().model
                key = chains_keys[i]
                chains[key] = model    

            distances_keys = distance_options
            distances = {}
            for i in range(number_of_options):
                key = distances_keys[i]
                value = line_edits[i]
                distances[key] = value

            self.create_disvis_input(chains, distances, pseudobonds, pb_lines)
            self.subset_dialog.close()

        ok_cancel = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)        
        ok_cancel.accepted.connect(get_parameters)
        ok_cancel.rejected.connect(self.disvis_dialog.close)  

        outer_layout.addLayout(models_layout)
        outer_layout.addLayout(distances_layout)
        outer_layout.addWidget(ok_cancel)

        self.disvis_dialog.setLayout(outer_layout)
        self.disvis_dialog.show()


    def create_disvis_input(self, chains, distances, pseudobonds, pb_lines=None):

        import re

        minimum = distances["Minimum"].text()
        maximum = distances["Maximum"].text()
        lines = []

        def write_line(atom1, atom2, sort=False):
            atoms = [atom1, atom2]
            number_of_atoms = len(atoms)
            atom_strings = [None] * number_of_atoms
            replace_with_space = [":", "@"]
            for i in range(number_of_atoms):
                atom = atoms[i]
                string = re.search("/.+", atom.string(style="command line")).group(0)
                string = string.replace("/", "")                
                for character in replace_with_space:
                    string = string.replace(character, " ")
                atom_strings[i] = string
            if sort:
                atom_strings.sort()
            line = atom_strings[0] + " " + atom_strings[1] + " " + minimum + " " + maximum

            return line

        if chains["Fixed"] == chains["Scanning"]:
            chain = chains["Fixed"]
            for pb in pseudobonds:
                if len(pb.models) != 1:
                    continue
                atom1, atom2 = pb.atoms
                if (atom1 not in chain.atoms or atom2 not in chain.atoms):
                    continue
                lines.append(write_line(atom1, atom2, sort=True))                
        else:
            for pb in pseudobonds:
                if len(pb.models) == 1:
                    continue
                atom1, atom2 = pb.atoms
                atoms = [atom1, atom2]
                for i in range(len(atoms)):
                    atoms[i].chain = object()
                    for chain in chains:
                        current_chain = chains[chain]
                        if atoms[i] in current_chain.atoms:
                            atoms[i].chain = current_chain
                if (atoms[0].chain == chains["Fixed"] and atoms[1].chain == chains["Scanning"]):
                    lines.append(write_line(atom1, atom2))
                elif (atoms[0].chain == chains["Scanning"] and atoms[1].chain == chains["Fixed"]):
                    lines.append(write_line(atom2, atom1))

        if len(lines) == 0:
            print("No pseudobonds match the criteria")
            return
        
        if pb_lines is not None:
            title = "Save pseudobonds and DisVis input"
            extension = "*.pb *.txt"
        else:
            title = "Save DisVis input"
            extension = "*.txt"

        self.save_subset(title, extension, [pb_lines, lines])

        self.disvis_dialog.close()
                

    def add_models(self, models):

        # The main tool window contains two treewidgets showing models;
        # the model selector for non-pseudobond structural models, and
        # the pbonds menu for pseudobond models. With this method, both
        # treewidgets of the main tool window can be filled.

        from PyQt5.QtWidgets import QTreeWidgetItem
        from PyQt5.QtCore import Qt

        for model in models:
            self.get_structure_type(model)
            if not hasattr(model, "structure_type"):
                continue
            model_name = model.name
            # For models in the model selector, show the model's
            # "id_string" attribute as ID
            checkstate = Qt.Checked
            if model.structure_type == "Non-pb":
                treewidget = self.model_selector
                column_1_text = model.id_string
            elif model.structure_type == "Pb":
                treewidget = self.pbonds_menu
                if not model.get_selected():
                    checkstate = Qt.Unchecked
                # For models in the pbonds menu that have been created
                # with XMAS, show the model's code
                # NB: if XMAS is closed and reopened in the
                # same session, we will start with a new, empty,
                # dictionary   
                if model_name in self.created_models.keys():
                    column_1_text = self.created_models[model_name]
                # Models in the pbonds menu that have not been created
                # with the current instance of XMAS will
                # not get a code
                else:
                    column_1_text = "N/A"
        
            model.item = QTreeWidgetItem(treewidget)
            item = model.item
            item.setText(0, model_name)
            item.setCheckState(0, checkstate)
            item.setText(1, column_1_text)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.model = model


    def get_structure_type(self, model):

        # Determine which treewidget the model belongs to

        from chimerax.atomic.structure import Structure
        from chimerax.atomic.pbgroup import PseudobondGroup

        # Structural, non-pseudobond models go in the model selector
        if (isinstance(model, Structure) 
                and not isinstance(model, PseudobondGroup)):
            model.structure_type = "Non-pb"
        # Models made from .pb files go in the pbonds_menu
        elif (isinstance(model, PseudobondGroup) and model.name[-3:] == ".pb"):
            model.structure_type = "Pb"          


    def trigger_handler(self):

        # Create trigger handlers for:
        # - change of selection, to change the CheckState of items in
        # the pbonds menu upon (de)selection of pseudobond models in
        # the session
        # - models being added to and removed from the session, to be
        # added and removed from the tool window

        from chimerax.core.selection import SELECTION_CHANGED
        from chimerax.core.models import ADD_MODELS, REMOVE_MODELS

        self.triggerset = self.session.triggers

        self.change_selection_handler = self.triggerset.add_handler(
            SELECTION_CHANGED,self.selection_handler
            )
        self.add_model_handler = self.triggerset.add_handler(
            ADD_MODELS, self.model_handler
            )
        self.remove_model_handler = self.triggerset.add_handler(
            REMOVE_MODELS, self.model_handler
            )


    def selection_handler(self, trigger, trigger_data):

        # Called upon change of model selection, to adjust the
        # CheckState of models in the pbonds menu, if necessary

        from PyQt5.QtCore import Qt

        for model in self.session.models:
            # Skip all models that are not in the pbonds menu
            if (not model.name[-3:] == ".pb" or isinstance(model, ColorScore)):
                continue
            item = model.item
            if model.selected:
                item.setCheckState(0, Qt.Checked)
            else:
                item.setCheckState(0, Qt.Unchecked)


    def model_handler(self, trigger, trigger_data):

        # Called when models are added to or removed from the session.
        # The trigger_data is a list of the models that were added or
        # removed

        # If models are added, call "add_models" method
        if trigger == "add models":
            self.add_models(trigger_data)
        # If models are removed, call "remove_models" method
        else:
            self.remove_models(trigger_data)


    def remove_models(self, models):

        # Called when models are removed from the session

        for model in models:
            if not hasattr(model, "item"):
                continue
            item = model.item
            treewidget = item.treeWidget()
            root = treewidget.invisibleRootItem()
            root.removeChild(item)             


    def cleanup(self):
        
        # Called when main tool window is closed. Trigger handlers are
        # removed to prevent errors when the trigger fires

        self.triggerset.remove_handler(self.change_selection_handler)
        self.triggerset.remove_handler(self.add_model_handler)
        self.triggerset.remove_handler(self.remove_model_handler)


class PeptidePair:
    
    def __init__(self, peptide_pair, xlinkx_score):
        self.peptides = [Peptide(peptide_pair[0]), Peptide(peptide_pair[1])]
        self.xlinkx_score = xlinkx_score


class Peptide:

    
    def __init__(self, peptide):

        # From each peptide, the sequence and the position of the
        # crosslinked residue is stored. Furthermore, any alignments on
        # model structures can be stored.

        if peptide.count("[") == 1:
            self.sequence = peptide.replace("[", "").replace("]", "")
            self.crosslink_position = peptide.index("[")    
        # When the crosslinked residue is the first residue in the
        # sequence, the sequence contains no brackets
        else:
            self.sequence = peptide
            self.crosslink_position = 0
        self.alignments = []


class Alignment:
    

    def __init__(
        self, start, end, first_residue_number, crosslink_position, model_id,
        chain):

        # Start and end position indicate the range of positions in the
        # sequence that is spanned by the peptide        
        self.start_position = start + first_residue_number
        self.end_position = end + first_residue_number
        # Position of the crosslinked residue in the sequence        
        self.crosslink_position = crosslink_position + first_residue_number
        residue = chain.residues[crosslink_position]
        atoms = residue.atoms
        for atom in atoms:
            if atom.name == "CA":
                self.atom = atom
        # String indicating on which model and chain the alignment was
        # found
        self.id_string = "#" + model_id + "/" + chain.chain_id


class PrePseudobond:

    # To avoid clashed with ChimeraX's Pseudobond class, this class is
    # named PrePseudobond
    
    
    def __init__(self, alignment1, alignment2, peptide_pair):

        # The crosslink positions of the two alignments dictate
        # between which atoms the pseudobond is formed
        self.pos1 = alignment1.crosslink_position
        self.pos2 = alignment2.crosslink_position
        self.id1 = alignment1.id_string
        self.id2 = alignment2.id_string
        self.atom1 = alignment1.atom
        self.atom2 = alignment2.atom        
        self.peptide_pair = peptide_pair
        self.xlinkx_score = peptide_pair.xlinkx_score
        # A string is created that will be one line in a .pb file
        self.line = self.create_pb_line()
        # Check for overlap between the two alignments
        self.is_overlapping = self.find_overlap(alignment1, alignment2)
        # Check whether the pseudobond is a self-link
        self.is_selflink = self.find_selflinks()

    
    def create_pb_line(self):

        pb_sorted = sorted([
            self.id1 + ":" + str(self.pos1) + "@CA",
            self.id2 + ":" + str(self.pos2) + "@CA"
            ])
        pb_line = pb_sorted[0] + " " + pb_sorted[1]
        
        return pb_line

    
    def find_overlap(self, alignment1, alignment2):

        if self.id1 != self.id2:
            is_overlapping = False
        else:
            maximum = max(alignment1.start_position, alignment2.start_position)
            minimum = min(alignment1.end_position, alignment2.end_position)
            if maximum < minimum:
                is_overlapping = True
            else:
                is_overlapping = False
        return is_overlapping

    
    def find_selflinks(self):

        is_selflink = False
        if (self.is_overlapping and self.pos1 == self.pos2):
            is_selflink = True

        return is_selflink


from chimerax.color_key.model import ColorKeyModel

class ColorScore(ColorKeyModel):

    def __init__(self, session, distances, name):

        super().__init__(session)
        self._rgbas_and_labels = self.get_rgbas_and_labels(distances)
        self._ticks = True
        self._tick_thickness = 2
        self._label_offset = -15
        self.name = "Key " + name


    def get_rgbas_and_labels(self, distances):

        from chimerax.core.colors import Colormap

        if distances is None:
            rgbas = [(1,0,0,1), (1,0.5,0,1), (1,1,0,1), (0.5,1,0,1), (0,1,0,1)]
            labels = ["0", " ", "100", " ", "≥200"]
        else:
            rgbas = [(1,1/3,1,1), (1,2/3,1,1), (1,1,1,1), (0.5,5/6,1,1), (0,2/3,1,1)]
            minimum = distances[0]
            maximum = distances[1]
            sum_values = minimum + maximum
            if not sum_values % 2 == 0:
                maximum += 1
            middle = int((minimum + maximum)/2)

            labels = [str(minimum), " ", str(middle), " ", str(maximum)]
            cmap = Colormap(None, ((1,1/3,1,1), (1,1,1,1), (0,2/3,1,1)))
            self.cmap = cmap.linear_range(minimum, maximum)

        number_of_labels = len(labels)
        _rgbas_and_labels = [None] * number_of_labels
        for i in range(number_of_labels):
            _rgbas_and_labels[i] = (rgbas[i], labels[i])

        return _rgbas_and_labels
        

class Slider:
    
    def __init__(self, value_type="distance", enabled=True, maximum=None, pbs=None):
        
        from PyQt5.QtWidgets import QGridLayout, QLabel, QLineEdit
        from qtrangeslider import QRangeSlider
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QIntValidator
        
        self.enabled = enabled
        self.layout = QGridLayout()
        if value_type == "distance":
            title = "Pseudobond distance (Å)"
        elif value_type == "score":
            title = "Max. XLinkX score"
        label = QLabel(title + ":")
        self.slider = QRangeSlider(Qt.Horizontal)
        self.setter_min = QLineEdit()
        self.setter_max = QLineEdit()
        
        self.layout.addWidget(label, 0, 0, 1, 4)
        self.layout.addWidget(self.slider, 1, 1, 1, 2)
        self.layout.addWidget(self.setter_min, 1, 0)
        self.layout.addWidget(self.setter_max, 1, 3)
        self.layout.setColumnMinimumWidth(1, 300)
        
        if not enabled:
            for i in range(self.layout.count()):
                widget = self.layout.itemAt(i).widget()
                widget.setEnabled(False)
            return
        
        self.slider.setRange(0, maximum)
        self.slider.setValue((0, maximum))
        signal = self.slider.valueChanged
        signal.connect(lambda: self.display_pseudobonds(value_type, pbs))
        signal.connect(self.adjust_setters)
        
        self.setters = [self.setter_min, self.setter_max]
        alignments = [Qt.AlignRight, Qt.AlignLeft]
        texts = ["0", str(maximum)]
        minimum = [True, False]
        for i in range(len(self.setters)):
            setter = self.setters[i]
            setter.setAlignment(alignments[i])
            setter.setValidator(QIntValidator())
            setter.setText(texts[i])
            setter.textChanged.connect(lambda: self.change_slider_value(minimum[i]))

        
    def display_pseudobonds(self, value_type, pbs):
        
        slider_values = self.slider.value()
        minimum = slider_values[0]
        maximum = slider_values[1]
        
        def get_distance(pb):
            return pb.length
        
        def get_score(pb):
            return pb.xlinkx_score
        
        if value_type == "distance":
            function = get_distance
        elif value_type == "score":
            function = get_score
            
        for pb in pbs:
            value = function(pb)
            if (value < minimum or value > maximum):
                pb.display = False
            else:
                pb.display = True

                
    def adjust_setters(self):
        
        values = self.slider.value()
        
        for i in range(len(values)):
            setter = self.setters[i]
            setter.setText(str(values[i]))

            
    def change_slider_value(self, minimum):

        print(self.setter_min.text())
        
        if minimum:
            values = (int(self.setter_min.text()), self.slider.value()[1])
        else:
            values = (self.slider.value()[0], int(self.setter_max.text()))
  
        self.slider.setValue(values)
