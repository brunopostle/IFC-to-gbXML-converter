#!/usr/bin/env python3
"""
Basic pytest tests for ifcgbxml converter.

These tests provide a foundation that can be expanded later with more
comprehensive test cases and mock IFC files.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from xml.dom import minidom
import numpy as np

# Import the module (path handled by conftest.py)
import ifcgbxml
from ifcgbxml import (
    XMLIdFormatter,
    IFCEntityAnalyzer,
    GeometryProcessor,
    GBXMLBuilder,
    create_gbxml,
    main
)


class TestXMLIdFormatter:
    """Test the XMLIdFormatter utility class."""
    
    def test_remove_unnecessary_characters(self):
        """Test removal of invalid XML characters."""
        test_cases = [
            ("test$id:name (1)", "test-idname_1"),
            ("simple", "simple"),
            ("$:()$", "--"),  # Fixed: only two replacements, not three
            ("", ""),
        ]
        
        for input_str, expected in test_cases:
            result = XMLIdFormatter.remove_unnecessary_characters(input_str)
            assert result == expected
    
    def test_fix_xml_campus(self):
        """Test campus ID formatting."""
        result = XMLIdFormatter.fix_xml_campus("test$id")
        assert result == "campus_test-id"
    
    def test_fix_xml_building(self):
        """Test building ID formatting."""
        result = XMLIdFormatter.fix_xml_building("test$id")
        assert result == "building_test-id"
    
    def test_fix_xml_storey(self):
        """Test storey ID formatting."""
        result = XMLIdFormatter.fix_xml_storey("test$id")
        assert result == "buildingstorey_test-id"
    
    def test_fix_xml_space(self):
        """Test space ID formatting."""
        result = XMLIdFormatter.fix_xml_space("test$id")
        assert result == "space_test-id"
    
    def test_fix_xml_boundary(self):
        """Test boundary ID formatting."""
        result = XMLIdFormatter.fix_xml_boundary("test$id")
        assert result == "boundary_test-id"
    
    def test_fix_xml_id(self):
        """Test generic ID formatting."""
        result = XMLIdFormatter.fix_xml_id("test$id")
        assert result == "id_test-id"
    
    def test_fix_xml_name(self):
        """Test name formatting."""
        result = XMLIdFormatter.fix_xml_name("test (name)")
        assert result == "object_test_name"
    
    def test_fix_xml_construction(self):
        """Test construction ID formatting."""
        result = XMLIdFormatter.fix_xml_construction("test$id")
        assert result == "construction_test-id"
    
    def test_fix_xml_layer(self):
        """Test layer ID formatting."""
        result = XMLIdFormatter.fix_xml_layer("test$id")
        assert result == "layer_test-id"


class TestIFCEntityAnalyzer:
    """Test the IFCEntityAnalyzer utility class."""
    
    def test_is_boundary_element(self):
        """Test boundary element detection."""
        # Mock IFC elements
        wall_mock = Mock()
        wall_mock.is_a.return_value = True
        
        non_boundary_mock = Mock()
        non_boundary_mock.is_a.return_value = False
        
        assert IFCEntityAnalyzer.is_boundary_element(wall_mock) == True
        assert IFCEntityAnalyzer.is_boundary_element(non_boundary_mock) == False
    
    @patch('ifcopenshell.util.element.get_psets')
    def test_is_external(self, mock_get_psets):
        """Test external element detection."""
        # Test external element
        mock_get_psets.return_value = {
            "Pset_WallCommon": {"IsExternal": True}
        }
        element_mock = Mock()
        assert IFCEntityAnalyzer.is_external(element_mock) == True
        
        # Test internal element
        mock_get_psets.return_value = {
            "Pset_WallCommon": {"IsExternal": False}
        }
        assert IFCEntityAnalyzer.is_external(element_mock) == False
        
        # Test element without IsExternal property
        mock_get_psets.return_value = {
            "Pset_WallCommon": {"SomeOtherProperty": "value"}
        }
        assert IFCEntityAnalyzer.is_external(element_mock) == False
    
    @patch('ifcopenshell.util.element.get_psets')
    def test_get_u_value(self, mock_get_psets):
        """Test U-value extraction."""
        # Test with ThermalTransmittance
        mock_get_psets.return_value = {
            "Pset_WallCommon": {"ThermalTransmittance": 0.5}
        }
        element_mock = Mock()
        assert IFCEntityAnalyzer.get_u_value(element_mock) == 0.5
        
        # Test with Heat Transfer Coefficient (U)
        mock_get_psets.return_value = {
            "Pset_WallCommon": {"Heat Transfer Coefficient (U)": 0.3}
        }
        assert IFCEntityAnalyzer.get_u_value(element_mock) == 0.3
        
        # Test without U-value
        mock_get_psets.return_value = {
            "Pset_WallCommon": {"SomeOtherProperty": "value"}
        }
        assert IFCEntityAnalyzer.get_u_value(element_mock) is None
    
    def test_get_element_or_type(self):
        """Test getting element type when available."""
        # Element with type
        type_mock = Mock()
        relating_type_mock = Mock()
        relating_type_mock.RelatingType = type_mock
        
        element_mock = Mock()
        element_mock.IsTypedBy = [relating_type_mock]
        
        result = IFCEntityAnalyzer.get_element_or_type(element_mock)
        assert result == type_mock
        
        # Element without type
        element_no_type_mock = Mock()
        element_no_type_mock.IsTypedBy = []
        
        result = IFCEntityAnalyzer.get_element_or_type(element_no_type_mock)
        assert result == element_no_type_mock


class TestGeometryProcessor:
    """Test the GeometryProcessor utility class."""
    
    def test_get_poly_loop(self):
        """Test PolyLoop XML element creation."""
        root = minidom.Document()
        vertices = [
            np.array([0.0, 0.0, 0.0]),
            np.array([1.0, 0.0, 0.0]),
            np.array([1.0, 1.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 0.0])  # Coincident start/end
        ]
        
        poly_loop = GeometryProcessor.get_poly_loop(root, vertices, linear_unit_scale=1.0)
        
        assert poly_loop.tagName == "PolyLoop"
        # Should have 4 CartesianPoints (coincident vertex removed)
        cartesian_points = poly_loop.getElementsByTagName("CartesianPoint")
        assert len(cartesian_points) == 4
        
        # Check first point coordinates
        first_point = cartesian_points[0]
        coordinates = first_point.getElementsByTagName("Coordinate")
        assert len(coordinates) == 3
        assert coordinates[0].firstChild.data == "0.0"
        assert coordinates[1].firstChild.data == "0.0"
        assert coordinates[2].firstChild.data == "0.0"
    
    def test_get_poly_loop_with_scale(self):
        """Test PolyLoop creation with unit scaling."""
        root = minidom.Document()
        vertices = [
            np.array([1.0, 1.0, 1.0]),
            np.array([2.0, 1.0, 1.0]),
            np.array([2.0, 2.0, 1.0])
        ]
        
        poly_loop = GeometryProcessor.get_poly_loop(root, vertices, linear_unit_scale=2.0)
        
        cartesian_points = poly_loop.getElementsByTagName("CartesianPoint")
        assert len(cartesian_points) == 3
        
        # Check first point coordinates are scaled
        first_point = cartesian_points[0]
        coordinates = first_point.getElementsByTagName("Coordinate")
        
        # Coordinates should be scaled
        assert coordinates[0].firstChild.data == "2.0"
        assert coordinates[1].firstChild.data == "2.0"
        assert coordinates[2].firstChild.data == "2.0"


class TestGBXMLBuilder:
    """Test the main GBXMLBuilder class."""
    
    @pytest.fixture
    def mock_ifc_file(self):
        """Create a mock IFC file for testing."""
        ifc_file = Mock()
        ifc_file.by_type.return_value = []
        return ifc_file
    
    @pytest.fixture
    def builder(self, mock_ifc_file):
        """Create a GBXMLBuilder instance for testing."""
        return GBXMLBuilder(mock_ifc_file)
    
    def test_initialization(self, builder, mock_ifc_file):
        """Test GBXMLBuilder initialization."""
        assert builder.ifc_file == mock_ifc_file
        assert builder.root is not None
        assert builder.gbxml is None
        assert builder.dict_id == {}
        assert builder.linear_unit_scale == 1.0
        assert builder.area_unit_scale == 1.0
        assert builder.volume_unit_scale == 1.0
        assert builder.imperial_units == False
    
    @patch('ifcopenshell.util.unit.calculate_unit_scale')
    @patch('ifcopenshell.util.unit.get_project_unit')
    @patch('ifcopenshell.util.unit.get_prefix_multiplier')
    def test_initialize_document(self, mock_get_prefix, mock_get_unit, mock_calc_scale, builder):
        """Test document initialization."""
        # Mock unit calculations
        mock_calc_scale.return_value = 1.0
        mock_get_prefix.return_value = 1.0
        
        # Create more detailed mock units
        mock_unit = Mock()
        mock_unit.is_a.side_effect = lambda unit_type: unit_type == "IfcSIUnit"
        mock_unit.Prefix = None
        mock_unit.Name = "METRE"
        mock_get_unit.return_value = mock_unit
        
        builder.initialize_document()
        
        assert builder.gbxml is not None
        assert builder.gbxml.tagName == "gbXML"
        assert builder.gbxml.getAttribute("xmlns") == "http://www.gbxml.org/schema"
        assert builder.gbxml.getAttribute("temperatureUnit") == "C"
        assert builder.gbxml.getAttribute("lengthUnit") == "Meters"
        assert builder.gbxml.getAttribute("areaUnit") == "SquareMeters"
        assert builder.gbxml.getAttribute("volumeUnit") == "CubicMeters"
        assert builder.gbxml.getAttribute("useSIUnitsForResults") == "true"
        assert builder.gbxml.getAttribute("version") == "6.01"
    
    def test_set_surface_type_wall_external(self, builder):
        """Test surface type setting for external wall."""
        # Initialize just the XML document without unit calculations
        builder.root = minidom.Document()
        builder.gbxml = builder.root.createElement("gbXML")
        builder.root.appendChild(builder.gbxml)
        
        surface = builder.root.createElement("Surface")
        
        # Mock IFC objects
        ifc_boundary = Mock()
        ifc_boundary.InternalOrExternalBoundary = "EXTERNAL"
        
        ifc_element = Mock()
        ifc_element.is_a.return_value = True
        
        with patch.object(ifc_element, 'is_a') as mock_is_a:
            mock_is_a.side_effect = lambda type_name: type_name == "IfcWall"
            
            builder.set_surface_type(surface, ifc_boundary, ifc_element)
            
            assert surface.getAttribute("surfaceType") == "ExteriorWall"
            assert surface.getAttribute("exposedToSun") == "true"
    
    def test_set_surface_type_wall_internal(self, builder):
        """Test surface type setting for internal wall."""
        # Initialize just the XML document without unit calculations
        builder.root = minidom.Document()
        builder.gbxml = builder.root.createElement("gbXML")
        builder.root.appendChild(builder.gbxml)
        
        surface = builder.root.createElement("Surface")
        
        # Mock IFC objects
        ifc_boundary = Mock()
        ifc_boundary.InternalOrExternalBoundary = "INTERNAL"
        
        ifc_element = Mock()
        
        with patch.object(ifc_element, 'is_a') as mock_is_a:
            mock_is_a.side_effect = lambda type_name: type_name == "IfcWall"
            
            with patch.object(IFCEntityAnalyzer, 'is_external', return_value=False):
                builder.set_surface_type(surface, ifc_boundary, ifc_element)
                
                assert surface.getAttribute("surfaceType") == "InteriorWall"
                assert surface.getAttribute("exposedToSun") == "false"
    
    def test_set_surface_type_roof(self, builder):
        """Test surface type setting for roof."""
        # Initialize just the XML document without unit calculations
        builder.root = minidom.Document()
        builder.gbxml = builder.root.createElement("gbXML")
        builder.root.appendChild(builder.gbxml)
        
        surface = builder.root.createElement("Surface")
        
        ifc_boundary = Mock()
        ifc_element = Mock()
        
        with patch.object(ifc_element, 'is_a') as mock_is_a:
            mock_is_a.side_effect = lambda type_name: type_name == "IfcRoof"
            
            builder.set_surface_type(surface, ifc_boundary, ifc_element)
            
            assert surface.getAttribute("surfaceType") == "Roof"
            assert surface.getAttribute("exposedToSun") == "true"
    
    @patch('ifcopenshell.util.unit.calculate_unit_scale')
    @patch('ifcopenshell.util.unit.get_project_unit')
    @patch('ifcopenshell.util.unit.get_prefix_multiplier')
    def test_build_creates_valid_xml(self, mock_get_prefix, mock_get_unit, mock_calc_scale, builder):
        """Test that build() creates a valid XML document."""
        # Mock unit calculations
        mock_calc_scale.return_value = 1.0
        mock_get_prefix.return_value = 1.0
        
        # Create more detailed mock units
        mock_unit = Mock()
        mock_unit.is_a.side_effect = lambda unit_type: unit_type == "IfcSIUnit"
        mock_unit.Prefix = None
        mock_unit.Name = "METRE"
        mock_get_unit.return_value = mock_unit
        
        # Mock empty IFC file
        builder.ifc_file.by_type.return_value = []
        
        with patch('os.getlogin', return_value='testuser'):
            root = builder.build()
            
            assert root is not None
            assert root.documentElement.tagName == "gbXML"
            
            # Check that DocumentHistory was added
            doc_history = root.getElementsByTagName("DocumentHistory")
            assert len(doc_history) == 1


class TestCreateGBXMLFunction:
    """Test the main create_gbxml function."""
    
    @patch('ifcopenshell.util.unit.calculate_unit_scale')
    @patch('ifcopenshell.util.unit.get_project_unit')
    @patch('ifcopenshell.util.unit.get_prefix_multiplier')
    def test_create_gbxml(self, mock_get_prefix, mock_get_unit, mock_calc_scale):
        """Test the create_gbxml function."""
        # Mock IFC file
        mock_ifc_file = Mock()
        mock_ifc_file.by_type.return_value = []
        
        # Mock unit calculations
        mock_calc_scale.return_value = 1.0
        mock_get_prefix.return_value = 1.0
        
        # Create more detailed mock units
        mock_unit = Mock()
        mock_unit.is_a.side_effect = lambda unit_type: unit_type == "IfcSIUnit"
        mock_unit.Prefix = None
        mock_unit.Name = "METRE"
        mock_get_unit.return_value = mock_unit
        
        with patch('os.getlogin', return_value='testuser'):
            result = create_gbxml(mock_ifc_file)
            
            assert result is not None
            assert result.documentElement.tagName == "gbXML"


class TestMainFunction:
    """Test the main console entry point."""
    
    @patch('sys.argv', ['ifcgbxml', 'input.ifc', 'output.xml'])
    @patch('ifcopenshell.open')
    @patch('builtins.open')
    def test_main_with_correct_args(self, mock_open, mock_ifc_open):
        """Test main function with correct arguments."""
        # Mock IFC file
        mock_ifc_file = Mock()
        mock_ifc_file.by_type.return_value = []
        mock_ifc_open.return_value = mock_ifc_file
        
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value = mock_file
        
        with patch('ifcgbxml.create_gbxml') as mock_create_gbxml:
            mock_root = Mock()
            mock_create_gbxml.return_value = mock_root
            
            # Should not raise an exception
            main()
            
            mock_ifc_open.assert_called_once_with('input.ifc')
            mock_create_gbxml.assert_called_once_with(mock_ifc_file)
            mock_root.writexml.assert_called_once()
    
    @patch('sys.argv', ['ifcgbxml'])
    @patch('builtins.print')
    def test_main_with_incorrect_args(self, mock_print):
        """Test main function with incorrect arguments."""
        main()
        mock_print.assert_called_once_with("Usage: ifcgbxml input.ifc output.xml")
    
    @patch('sys.argv', ['ifcgbxml', 'one_arg'])
    @patch('builtins.print')
    def test_main_with_one_arg(self, mock_print):
        """Test main function with only one argument."""
        main()
        mock_print.assert_called_once_with("Usage: ifcgbxml input.ifc output.xml")


class TestIntegration:
    """Integration tests that test multiple components together."""
    
    @patch('ifcopenshell.util.unit.calculate_unit_scale')
    @patch('ifcopenshell.util.unit.get_project_unit')
    @patch('ifcopenshell.util.unit.get_prefix_multiplier')
    def test_xml_id_consistency(self, mock_get_prefix, mock_get_unit, mock_calc_scale):
        """Test that XML IDs are consistent throughout the document."""
        # Mock unit calculations
        mock_calc_scale.return_value = 1.0
        mock_get_prefix.return_value = 1.0
        
        # Create more detailed mock units
        mock_unit = Mock()
        mock_unit.is_a.side_effect = lambda unit_type: unit_type == "IfcSIUnit"
        mock_unit.Prefix = None
        mock_unit.Name = "METRE"
        mock_get_unit.return_value = mock_unit
        
        # Create a mock IFC file with some basic elements
        mock_ifc_file = Mock()
        
        # Mock a site
        mock_site = Mock()
        mock_site.GlobalId = "test_site_id"
        mock_site.RefLatitude = [53, 23, 0]
        mock_site.RefLongitude = [1, 28, 0]
        mock_site.RefElevation = 75.0
        mock_site.SiteAddress = None
        mock_site.IsDecomposedBy = []
        
        mock_ifc_file.by_type.side_effect = lambda entity_type: {
            "IfcSite": [mock_site],
            "IfcRelSpaceBoundary": []
        }.get(entity_type, [])
        
        builder = GBXMLBuilder(mock_ifc_file)
        
        with patch('os.getlogin', return_value='testuser'):
            root = builder.build()
            
            # Check that the campus element was created with correct ID
            campus_elements = root.getElementsByTagName("Campus")
            assert len(campus_elements) == 1
            
            expected_id = XMLIdFormatter.fix_xml_campus("test_site_id")
            assert campus_elements[0].getAttribute("id") == expected_id
            
            # Check that the ID is stored in the builder's dictionary
            assert expected_id in builder.dict_id


if __name__ == "__main__":
    pytest.main([__file__])
