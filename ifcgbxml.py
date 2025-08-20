#!/usr/bin/python3

import ifcopenshell.util.placement
import ifcopenshell.util.shape
import ifcopenshell.util.unit
import ifcopenshell.util.element
import ifcopenshell.geom
import numpy as np
import datetime
import time
import sys
import getpass
from xml.dom import minidom

# Copyright (C) 2016-2023
# Maarten Visschers <maartenvisschers@hotmail.com>
# Bruno Postle <bruno@postle.net>
# Tokarzewski <bartlomiej.tokarzewski@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

# Constants
BOUNDARY_ELEMENT_TYPES = [
    "IfcWall",
    "IfcColumn",
    "IfcMember",
    "IfcVirtualElement",
    "IfcPlate",
    "IfcCurtainWall",
    "IfcWindow",
    "IfcSlab",
    "IfcRoof",
    "IfcCovering",
]

# Helper functions
get_pset = ifcopenshell.util.element.get_pset


class XMLIdFormatter:
    """Handles formatting of element IDs for XML compatibility."""

    @staticmethod
    def remove_unnecessary_characters(element):
        """Remove invalid XML id characters from a string."""
        char_to_replace = {"$": "-", ":": "", " ": "_", "(": "", ")": ""}
        for key, value in char_to_replace.items():
            element = element.replace(key, value)
        return element

    @staticmethod
    def fix_xml_campus(element):
        return "campus_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_building(element):
        return "building_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_storey(element):
        return "buildingstorey_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_space(element):
        return "space_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_boundary(element):
        return "boundary_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_id(element):
        return "id_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_name(element):
        return "object_" + XMLIdFormatter.remove_unnecessary_characters(element)

    @staticmethod
    def fix_xml_construction(element):
        return "construction_" + element.replace("$", "-")

    @staticmethod
    def fix_xml_layer(element):
        return "layer_" + element.replace("$", "-")


class IFCEntityAnalyzer:
    """Handles analysis of IFC entities and their properties."""

    @staticmethod
    def is_boundary_element(ifc_building_element):
        """Check if an element is a boundary element."""
        for ifc_class in BOUNDARY_ELEMENT_TYPES:
            if ifc_building_element.is_a(ifc_class):
                return True
        return False

    @staticmethod
    def is_external(ifc_building_element):
        """Check if an element is external."""
        psets = ifcopenshell.util.element.get_psets(
            ifc_building_element, psets_only=True, should_inherit=True
        )
        for pset in psets:
            if "IsExternal" in psets[pset] and psets[pset]["IsExternal"]:
                return True
        return False

    @staticmethod
    def get_u_value(ifc_building_element):
        """Get the thermal transmittance (U-value) of an element."""
        psets = ifcopenshell.util.element.get_psets(
            ifc_building_element, psets_only=True, should_inherit=True
        )
        for pset in psets:
            for prop in psets[pset]:
                if (
                    prop == "ThermalTransmittance"
                    or prop == "Heat Transfer Coefficient (U)"
                ):
                    return psets[pset][prop]
        return None

    @staticmethod
    def get_parent_boundary(ifc_rel_space_boundary):
        """Get the parent boundary of a space boundary."""
        ifc_building_element = ifc_rel_space_boundary.RelatedBuildingElement
        if hasattr(ifc_rel_space_boundary, "ParentBoundary"):
            # IFC4
            return ifc_rel_space_boundary.ParentBoundary
        elif (
            ifc_building_element.FillsVoids
            and ifc_building_element.FillsVoids[0].RelatingOpeningElement.VoidsElements
        ):
            # IFC2X3
            for ifc_boundary in (
                ifc_building_element.FillsVoids[0]
                .RelatingOpeningElement.VoidsElements[0]
                .RelatingBuildingElement.ProvidesBoundaries
            ):
                if ifc_boundary.RelatingSpace == ifc_rel_space_boundary.RelatingSpace:
                    return ifc_boundary
        return None

    @staticmethod
    def get_material_layer_set(ifc_building_element):
        """Get the material layer set of an element."""
        ifc_building_element = IFCEntityAnalyzer.get_element_or_type(
            ifc_building_element
        )
        for association in ifc_building_element.HasAssociations:
            if association.is_a("IfcRelAssociatesMaterial"):
                if association.RelatingMaterial.is_a("IfcMaterialLayerSet"):
                    return association.RelatingMaterial
                elif association.RelatingMaterial.is_a("IfcMaterialLayerSetUsage"):
                    return association.RelatingMaterial.ForLayerSet
        return None

    @staticmethod
    def get_element_or_type(ifc_building_element):
        """Get the element type if available, otherwise the element itself."""
        if (
            hasattr(ifc_building_element, "IsTypedBy")
            and ifc_building_element.IsTypedBy
        ):
            return ifc_building_element.IsTypedBy[0].RelatingType
        return ifc_building_element

    @staticmethod
    def get_area_property(ifc_space):
        """Get the area property of a space."""
        return (
            get_pset(
                # IFC4
                ifc_space,
                "Qto_SpaceBaseQuantities",
                prop="NetFloorArea",
            )
            or get_pset(
                # IFC4
                ifc_space,
                "Pset_SpaceCommon",
                prop="NetPlannedArea",
            )
            or get_pset(
                # IFC2X3
                ifc_space,
                "BaseQuantities",
                prop="NetFloorArea",
            )
            or get_pset(
                # IFC2X3
                ifc_space,
                "Dimensions",
                prop="Area",
            )
        )

    @staticmethod
    def get_volume_property(ifc_space):
        """Get the volume property of a space."""
        return (
            get_pset(
                # IFC4
                ifc_space,
                "Qto_SpaceBaseQuantities",
                prop="NetVolume",
            )
            or get_pset(
                # IFC2X3
                ifc_space,
                "BaseQuantities",
                prop="GrossVolume",
            )
            or get_pset(
                # IFC2X3
                ifc_space,
                "Dimensions",
                prop="Volume",
            )
        )

    @staticmethod
    def get_transmittance(ifc_building_element):
        """Get the transmittance property of an element."""
        return (
            get_pset(
                # IFC4
                ifc_building_element,
                "Pset_DoorCommon",
                prop="GlazingAreaFraction",
            )
            or get_pset(
                # IFC4
                ifc_building_element,
                "Pset_WindowCommon",
                prop="GlazingAreaFraction",
            )
            or get_pset(
                # IFC2X3
                ifc_building_element,
                "Analytical Properties(Type)",
                prop="Visual Light Transmittance",
            )
        )

    @staticmethod
    def get_solar_heat_gain_coeff(ifc_building_element):
        """Get the solar heat gain coefficient property of an element."""
        return get_pset(
            # IFC2X3
            ifc_building_element,
            "Analytical Properties(Type)",
            prop="Solar Heat Gain Coefficient",
        )

    @staticmethod
    def get_absorptance(ifc_building_element):
        """Get the absorptance property of an element."""
        return get_pset(
            ifc_building_element,
            "Analytical Properties(Type)",
            prop="Absorptance",
        )

    @staticmethod
    def get_r_value(ifc_material):
        """Get the R-value property of a material."""
        return get_pset(
            # IFC4
            ifc_material,
            "Pset_MaterialEnergy",
            prop="ThermalConductivityTemperatureDerivative",
        ) or get_pset(
            # IFC2X3
            ifc_material,
            "Analytical Properties(Type)",
            prop="Thermal Resistance (R)",
        )

    @staticmethod
    def get_material_u_value(ifc_material):
        """Get the U-value property of a material."""
        return get_pset(
            # IFC2X3
            ifc_material,
            "Analytical Properties(Type)",
            prop="Heat Transfer Coefficient (U)",
        )


class GeometryProcessor:
    """Handles geometry processing for boundary vertices."""

    @staticmethod
    def get_boundary_vertices(ifc_rel_space_boundary):
        """Get the boundary vertices of a space boundary."""
        ifc_curve = ifc_rel_space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
        if ifc_curve.is_a("IfcFaceSurface"):
            # FIXME assumes Bound is IfcPolyLoop, could also be IfcEdgeLoop or IfcVertexLoop
            ifc_points = ifc_curve.Bounds[0].Bound.Polygon
            plane_coords = [v.Coordinates for v in ifc_points]
            ifc_plane = ifc_curve.FaceSurface
        elif ifc_curve.is_a("IfcCurveBoundedPlane"):
            # assumes OuterBoundary is IfcIndexedPolyCurve or IfcPolyline
            if ifc_curve.OuterBoundary.is_a("IfcPolyline"):
                plane_coords = [
                    point.Coordinates for point in ifc_curve.OuterBoundary.Points
                ]
            elif ifc_curve.OuterBoundary.is_a("IfcIndexedPolyCurve"):
                plane_coords = ifc_curve.OuterBoundary.Points[0]
            else:
                return []
            ifc_plane = ifc_curve.BasisSurface
        else:
            settings = ifcopenshell.geom.settings()
            shape = ifcopenshell.geom.create_shape(settings, ifc_curve)
            vertices = ifcopenshell.util.shape.get_vertices(shape)
            verts = [[v[0], v[1], v[2], 1.0] for v in vertices]
            matrix = ifcopenshell.util.placement.get_local_placement(
                ifc_rel_space_boundary.RelatingSpace.Decomposes[
                    0
                ].RelatingObject.ObjectPlacement
            )
            return [(matrix @ v)[0:3] for v in verts]

        space_matrix = ifcopenshell.util.placement.get_local_placement(
            ifc_rel_space_boundary.RelatingSpace.ObjectPlacement
        )
        plane_matrix = ifcopenshell.util.placement.get_axis2placement(
            ifc_plane.Position
        )
        plane_vertices = [
            np.array(v + (0, 1)) if len(v) == 2 else np.array(v + (1,))
            for v in plane_coords
        ]
        vertices = [(space_matrix @ plane_matrix @ v)[0:3] for v in plane_vertices]
        if (
            np.dot(
                np.cross(vertices[1] - vertices[0], vertices[-1] - vertices[0]),
                (plane_matrix @ np.array([0, 0, 1, 0]))[0:3],
            )
            < -1e-6
        ):
            vertices.reverse()
        return vertices

    @staticmethod
    def get_poly_loop(root, vertices, linear_unit_scale=1.0):
        """Create a PolyLoop XML element from vertices."""
        poly_loop = root.createElement("PolyLoop")
        # gbXML PolyLoops don't have coincident start/end vertices
        if np.allclose(vertices[0], vertices[-1]):
            del vertices[-1]
        for v in vertices:
            x, y, z = v
            cartesian_point = root.createElement("CartesianPoint")
            for c in x, y, z:
                if "e-" in str(c):
                    c = 0.0
                c *= linear_unit_scale
                coordinate = root.createElement("Coordinate")
                coordinate.appendChild(root.createTextNode(str(c)))
                cartesian_point.appendChild(coordinate)
            poly_loop.appendChild(cartesian_point)
        return poly_loop


class GBXMLBuilder:
    """Main class to build gbXML document from IFC file."""

    def __init__(self, ifc_file):
        self.ifc_file = ifc_file
        self.root = minidom.Document()
        self.gbxml = None
        self.dict_id = {}  # Dictionary to store all gbXML element Ids
        self.linear_unit_scale = 1.0
        self.area_unit_scale = 1.0
        self.volume_unit_scale = 1.0
        self.imperial_units = False

    def initialize_document(self):
        """Initialize the gbXML document with basic attributes."""
        self.gbxml = self.root.createElement("gbXML")
        self.root.appendChild(self.gbxml)

        self.gbxml.setAttribute("xmlns", "http://www.gbxml.org/schema")
        self.gbxml.setAttribute("temperatureUnit", "C")
        self.gbxml.setAttribute("lengthUnit", "Meters")
        self.gbxml.setAttribute("areaUnit", "SquareMeters")
        self.gbxml.setAttribute("volumeUnit", "CubicMeters")
        self.gbxml.setAttribute("useSIUnitsForResults", "true")
        self.gbxml.setAttribute("version", "0.37")

        self.initialize_unit_scales()

    def initialize_unit_scales(self):
        """Initialize unit scale factors from the IFC file."""
        self.linear_unit_scale = ifcopenshell.util.unit.calculate_unit_scale(
            self.ifc_file
        )

        area_unit = ifcopenshell.util.unit.get_project_unit(self.ifc_file, "AREAUNIT")
        self.area_unit_scale = 1.0
        while area_unit.is_a("IfcConversionBasedUnit"):
            self.area_unit_scale *= (
                area_unit.ConversionFactor.ValueComponent.wrappedValue
            )
            area_unit = area_unit.ConversionFactor.UnitComponent
        if area_unit.is_a("IfcSIUnit"):
            self.area_unit_scale *= ifcopenshell.util.unit.get_prefix_multiplier(
                area_unit.Prefix
            )

        volume_unit = ifcopenshell.util.unit.get_project_unit(
            self.ifc_file, "VOLUMEUNIT"
        )
        self.volume_unit_scale = 1.0
        while volume_unit.is_a("IfcConversionBasedUnit"):
            self.volume_unit_scale *= (
                volume_unit.ConversionFactor.ValueComponent.wrappedValue
            )
            volume_unit = volume_unit.ConversionFactor.UnitComponent
        if volume_unit.is_a("IfcSIUnit"):
            self.volume_unit_scale *= ifcopenshell.util.unit.get_prefix_multiplier(
                volume_unit.Prefix
            )

        # NOTE crude check for imperial units
        length_unit = ifcopenshell.util.unit.get_project_unit(
            self.ifc_file, "LENGTHUNIT"
        )
        self.imperial_units = (
            length_unit.Name in ["inch", "foot", "yard"]
            if hasattr(length_unit, "Name")
            else False
        )

    def set_surface_type(self, surface, ifc_rel_space_boundary, ifc_building_element):
        """Set the surface type attribute based on the building element type."""
        if ifc_building_element.is_a("IfcCovering"):
            # NOTE assumes all coverings with a related space boundary are ceilings
            surface.setAttribute("surfaceType", "Ceiling")

        elif ifc_building_element.is_a("IfcRoof"):
            surface.setAttribute("surfaceType", "Roof")
            surface.setAttribute("exposedToSun", "true")

        elif ifc_building_element.is_a("IfcColumn"):
            surface.setAttribute("surfaceType", "EmbeddedColumn")

        elif ifc_building_element.is_a("IfcSlab"):
            if (
                ifc_rel_space_boundary.InternalOrExternalBoundary == "EXTERNAL_EARTH"
                or IFCEntityAnalyzer.is_external(ifc_building_element)
            ):
                surface.setAttribute("surfaceType", "SlabOnGrade")
            else:
                surface.setAttribute("surfaceType", "InteriorFloor")

        elif ifc_building_element.is_a("IfcWall"):
            if (
                ifc_rel_space_boundary.InternalOrExternalBoundary == "EXTERNAL"
                or IFCEntityAnalyzer.is_external(ifc_building_element)
            ):
                surface.setAttribute("surfaceType", "ExteriorWall")
                surface.setAttribute("exposedToSun", "true")
            elif ifc_rel_space_boundary.InternalOrExternalBoundary == "EXTERNAL_FIRE":
                surface.setAttribute("surfaceType", "InteriorWall")
                surface.setAttribute("exposedToSun", "false")
            else:
                surface.setAttribute("surfaceType", "InteriorWall")
                surface.setAttribute("exposedToSun", "false")

        elif ifc_building_element.is_a("IfcCurtainWall"):
            surface.setAttribute("surfaceType", "ExteriorWall")
            surface.setAttribute("exposedToSun", "true")

        elif ifc_building_element.is_a("IfcVirtualElement"):
            surface.setAttribute("surfaceType", "Air")

        else:
            print("WARNING: setting surfaceType to Undefined")
            surface.setAttribute("surfaceType", "Undefined")
            if IFCEntityAnalyzer.is_external(ifc_building_element):
                surface.setAttribute("exposedToSun", "true")

    def build_campus(self):
        """Build the Campus elements."""
        for ifc_site in self.ifc_file.by_type("IfcSite"):
            # Set default location if missing
            if ifc_site.RefLongitude is None:
                print("WARNING: missing RefLongitude")
                ifc_site.RefLatitude = [53, 23, 0]
                ifc_site.RefLongitude = [1, 28, 0]
                ifc_site.RefElevation = 75.0

            campus = self.root.createElement("Campus")
            campus.setAttribute("id", XMLIdFormatter.fix_xml_campus(ifc_site.GlobalId))
            self.gbxml.appendChild(campus)

            self.dict_id[XMLIdFormatter.fix_xml_campus(ifc_site.GlobalId)] = campus

            # Add location information
            self.build_location(campus, ifc_site)

            # Process buildings in the site
            self.build_buildings(campus, ifc_site)

    def build_location(self, campus, ifc_site):
        """Build the Location element for a site."""
        location = self.root.createElement("Location")
        campus.appendChild(location)

        # Add longitude
        longitude = self.root.createElement("Longitude")
        longitude.appendChild(self.root.createTextNode(str(ifc_site.RefLongitude[0])))
        location.appendChild(longitude)

        # Add latitude
        latitude = self.root.createElement("Latitude")
        latitude.appendChild(self.root.createTextNode(str(ifc_site.RefLatitude[0])))
        location.appendChild(latitude)

        # Add elevation
        elevation = self.root.createElement("Elevation")
        elevation.appendChild(self.root.createTextNode(str(ifc_site.RefElevation)))
        location.appendChild(elevation)

        # Add postal code and name
        ifc_postal_address = ifc_site.SiteAddress
        zipcode = self.root.createElement("ZipcodeOrPostalCode")
        location.appendChild(zipcode)

        if ifc_postal_address:
            zipcode.appendChild(self.root.createTextNode(ifc_postal_address.PostalCode))

            name = self.root.createElement("Name")
            name.appendChild(
                self.root.createTextNode(
                    str(ifc_postal_address.Region)
                    + ", "
                    + str(ifc_postal_address.Country)
                )
            )
            location.appendChild(name)
        else:
            print("WARNING: missing SiteAddress")
            zipcode.appendChild(self.root.createTextNode("S1 2GH"))

    def build_buildings(self, campus, ifc_site):
        """Build the Building elements for a site."""
        if not ifc_site.IsDecomposedBy:
            print("WARNING: IfcSite empty")
            return

        for ifc_building in ifc_site.IsDecomposedBy[0].RelatedObjects:
            if not ifc_building.is_a("IfcBuilding"):
                continue

            building = self.root.createElement("Building")
            building.setAttribute(
                "id", XMLIdFormatter.fix_xml_building(ifc_building.GlobalId)
            )
            building.setAttribute("buildingType", "Unknown")
            campus.appendChild(building)

            self.dict_id[XMLIdFormatter.fix_xml_building(ifc_building.GlobalId)] = (
                building
            )

            # Add address information
            ifc_postal_address = ifc_building.BuildingAddress
            if ifc_postal_address:
                street_address = self.root.createElement("StreetAddress")
                street_address.appendChild(
                    self.root.createTextNode(
                        str(ifc_postal_address.Region)
                        + ", "
                        + str(ifc_postal_address.Country)
                    )
                )
                building.appendChild(street_address)

            # Process building storeys
            self.build_building_storeys(building, ifc_building)

    def build_building_storeys(self, building, ifc_building):
        """Build the BuildingStorey elements for a building."""
        if not ifc_building.IsDecomposedBy:
            print("WARNING: IfcBuilding is empty")
            return

        for ifc_building_storey in ifc_building.IsDecomposedBy[0].RelatedObjects:
            if not ifc_building_storey.is_a("IfcBuildingStorey"):
                continue

            building_storey = self.root.createElement("BuildingStorey")
            building_storey.setAttribute(
                "id", XMLIdFormatter.fix_xml_storey(ifc_building_storey.GlobalId)
            )
            building.appendChild(building_storey)

            self.dict_id[
                XMLIdFormatter.fix_xml_storey(ifc_building_storey.GlobalId)
            ] = building_storey

            # Add name
            name = self.root.createElement("Name")
            name.appendChild(
                self.root.createTextNode(ifc_building_storey.Name or "Unnamed")
            )
            building_storey.appendChild(name)

            # Add level
            level = self.root.createElement("Level")
            level.appendChild(
                self.root.createTextNode(
                    str(
                        ifcopenshell.util.placement.get_storey_elevation(
                            ifc_building_storey
                        )
                    )
                )
            )
            building_storey.appendChild(level)

            # Process spaces in the building storey
            self.build_spaces(building, ifc_building_storey)

    def build_spaces(self, building, ifc_building_storey):
        """Build the Space elements for a building storey."""
        if not ifc_building_storey.IsDecomposedBy:
            print("WARNING: IfcBuildingStorey is empty")
            return

        for ifc_space in ifc_building_storey.IsDecomposedBy[0].RelatedObjects:
            if not ifc_space.is_a("IfcSpace"):
                continue

            space = self.root.createElement("Space")
            space.setAttribute("id", XMLIdFormatter.fix_xml_space(ifc_space.GlobalId))
            building.appendChild(space)

            self.dict_id[XMLIdFormatter.fix_xml_space(ifc_space.GlobalId)] = space

            space.setAttribute(
                "buildingStoreyIdRef",
                XMLIdFormatter.fix_xml_storey(
                    ifc_space.Decomposes[0].RelatingObject.GlobalId
                ),
            )

            # Add area information
            pset_area = IFCEntityAnalyzer.get_area_property(ifc_space)
            if pset_area:
                area = self.root.createElement("Area")
                area.setAttribute("unit", "SquareMeters")
                area.appendChild(
                    self.root.createTextNode(str(pset_area * self.area_unit_scale))
                )
                space.appendChild(area)
            else:
                print("WARNING: IfcSpace has no Area")

            # Add volume information
            pset_volume = IFCEntityAnalyzer.get_volume_property(ifc_space)
            if pset_volume:
                volume = self.root.createElement("Volume")
                volume.setAttribute("unit", "CubicMeters")
                volume.appendChild(
                    self.root.createTextNode(str(pset_volume * self.volume_unit_scale))
                )
                space.appendChild(volume)
            else:
                print("WARNING: IfcSpace has no Volume")

            # Add name
            name = self.root.createElement("Name")
            name.appendChild(self.root.createTextNode(ifc_space.Name or "Unnamed"))
            space.appendChild(name)

            if not ifc_space.BoundedBy:
                print("WARNING: IfcSpace not Bounded")
                continue

            # Process space boundaries
            self.build_space_boundaries(space, ifc_space)

    def build_space_boundaries(self, space, ifc_space):
        """Build the SpaceBoundary elements for a space."""
        for ifc_rel_space_boundary in ifc_space.BoundedBy:
            if IFCEntityAnalyzer.get_parent_boundary(ifc_rel_space_boundary):
                continue

            # Make sure a 'SpaceBoundary' is representing an actual element
            if ifc_rel_space_boundary.RelatedBuildingElement is None:
                print("WARNING: SpaceBoundary has no RelatedBuildingElement")
                continue

            if (
                ifc_rel_space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                is None
            ):
                print("WARNING: SpaceBoundary has no geometry")
                continue

            # Require 2nd Level boundaries
            if not (
                ifc_rel_space_boundary.Name == "2ndLevel"
                or ifc_rel_space_boundary.is_a("IfcRelSpaceBoundary2ndLevel")
            ):
                print("WARNING: SpaceBoundary not 2ndLevel")
                continue

            vertices = GeometryProcessor.get_boundary_vertices(ifc_rel_space_boundary)
            if not len(vertices):
                continue

            ifc_building_element = ifc_rel_space_boundary.RelatedBuildingElement

            # Create 'SpaceBoundary' elements for boundary elements
            if IFCEntityAnalyzer.is_boundary_element(ifc_building_element):
                space_boundary = self.root.createElement("SpaceBoundary")
                space_boundary.setAttribute("isSecondLevelBoundary", "true")
                space_boundary.setAttribute(
                    "surfaceIdRef",
                    XMLIdFormatter.fix_xml_id(ifc_rel_space_boundary.GlobalId),
                )
                space.appendChild(space_boundary)

                planar_geometry = self.root.createElement("PlanarGeometry")
                space_boundary.appendChild(planar_geometry)

                planar_geometry.appendChild(
                    GeometryProcessor.get_poly_loop(
                        self.root, vertices, linear_unit_scale=self.linear_unit_scale
                    )
                )
            else:
                print("WARNING: Element is not a Boundary Element")

    def build_surfaces(self):
        """Build the Surface elements from space boundaries."""
        for ifc_rel_space_boundary in self.ifc_file.by_type("IfcRelSpaceBoundary"):
            ifc_building_element = ifc_rel_space_boundary.RelatedBuildingElement

            # Make sure a 'SpaceBoundary' is representing an actual element
            if ifc_building_element is None:
                continue

            if (
                ifc_rel_space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                is None
            ):
                continue

            if ifc_rel_space_boundary.RelatingSpace is None:
                continue

            # require 2nd Level boundaries
            if not (
                ifc_rel_space_boundary.Name == "2ndLevel"
                or ifc_rel_space_boundary.is_a("IfcRelSpaceBoundary2ndLevel")
            ):
                continue

            if IFCEntityAnalyzer.get_parent_boundary(ifc_rel_space_boundary):
                continue

            vertices = GeometryProcessor.get_boundary_vertices(ifc_rel_space_boundary)
            if not len(vertices):
                continue

            # Create Surface elements for boundary elements
            if IFCEntityAnalyzer.is_boundary_element(ifc_building_element):
                self.create_surface_element(
                    ifc_rel_space_boundary, ifc_building_element, vertices
                )

    def create_surface_element(
        self, ifc_rel_space_boundary, ifc_building_element, vertices
    ):
        """Create a Surface element for a space boundary."""
        surface = self.root.createElement("Surface")
        surface.setAttribute(
            "id", XMLIdFormatter.fix_xml_id(ifc_rel_space_boundary.GlobalId)
        )
        self.dict_id[XMLIdFormatter.fix_xml_id(ifc_rel_space_boundary.GlobalId)] = (
            surface
        )

        # Set the surface type based on the building element type
        self.set_surface_type(surface, ifc_rel_space_boundary, ifc_building_element)

        # Set construction ID reference
        ifc_material_layer_set = IFCEntityAnalyzer.get_material_layer_set(
            ifc_building_element
        )

        if ifc_material_layer_set:
            surface.setAttribute(
                "constructionIdRef",
                XMLIdFormatter.fix_xml_construction(str(ifc_material_layer_set.id())),
            )
        else:
            # elements without a layer set may have u-value property
            ifc_building_element_type = IFCEntityAnalyzer.get_element_or_type(
                ifc_building_element
            )
            surface.setAttribute(
                "constructionIdRef",
                XMLIdFormatter.fix_xml_construction(
                    str(ifc_building_element_type.id())
                ),
            )

        # Add name
        name = self.root.createElement("Name")
        name.appendChild(
            self.root.createTextNode(
                XMLIdFormatter.fix_xml_boundary(ifc_rel_space_boundary.GlobalId)
            )
        )
        surface.appendChild(name)

        # Add adjacent space reference
        adjacent_space_id = self.root.createElement("AdjacentSpaceId")
        adjacent_space_id.setAttribute(
            "spaceIdRef",
            XMLIdFormatter.fix_xml_space(ifc_rel_space_boundary.RelatingSpace.GlobalId),
        )
        surface.appendChild(adjacent_space_id)

        # Add geometry
        planar_geometry = self.root.createElement("PlanarGeometry")
        surface.appendChild(planar_geometry)
        planar_geometry.appendChild(
            GeometryProcessor.get_poly_loop(
                self.root, vertices, linear_unit_scale=self.linear_unit_scale
            )
        )

        # Add CAD object ID
        cad_object_id = self.root.createElement("CADObjectId")
        cad_object_id.appendChild(
            self.root.createTextNode(
                XMLIdFormatter.fix_xml_boundary(ifc_rel_space_boundary.GlobalId)
            )
        )
        surface.appendChild(cad_object_id)

        self.gbxml.appendChild(surface)

    def build_openings(self):
        """Build the Opening elements for windows and doors."""
        opening_id = 1
        for ifc_rel_space_boundary in self.ifc_file.by_type("IfcRelSpaceBoundary"):
            ifc_building_element = ifc_rel_space_boundary.RelatedBuildingElement

            # Make sure a 'SpaceBoundary' is representing an actual element
            if ifc_building_element is None:
                continue

            if (
                ifc_rel_space_boundary.ConnectionGeometry.SurfaceOnRelatingElement
                is None
            ):
                continue

            vertices = GeometryProcessor.get_boundary_vertices(ifc_rel_space_boundary)
            if not len(vertices):
                continue

            if ifc_building_element.is_a() in ["IfcWindow", "IfcDoor"]:
                ifc_parent_boundary = IFCEntityAnalyzer.get_parent_boundary(
                    ifc_rel_space_boundary
                )

                if not ifc_parent_boundary:
                    print("WARNING: IfcWindow/IfcDoor boundary has no parent boundary")
                    continue

                ifc_building_element_type = IFCEntityAnalyzer.get_element_or_type(
                    ifc_building_element
                )

                opening = self.root.createElement("Opening")
                self.dict_id[
                    XMLIdFormatter.fix_xml_id(ifc_rel_space_boundary.GlobalId)
                ] = opening

                opening.setAttribute(
                    "windowTypeIdRef",
                    XMLIdFormatter.fix_xml_id(ifc_building_element_type.GlobalId),
                )

                if ifc_building_element.is_a("IfcWindow"):
                    opening.setAttribute("openingType", "OperableWindow")
                elif ifc_building_element.is_a("IfcDoor"):
                    opening.setAttribute("openingType", "NonSlidingDoor")

                opening.setAttribute("id", f"Opening{opening_id}")
                opening_id += 1

                # Add geometry
                planar_geometry = self.root.createElement("PlanarGeometry")
                opening.appendChild(planar_geometry)

                planar_geometry.appendChild(
                    GeometryProcessor.get_poly_loop(
                        self.root, vertices, linear_unit_scale=self.linear_unit_scale
                    )
                )

                # Add name
                name = self.root.createElement("Name")
                name.appendChild(
                    self.root.createTextNode(
                        XMLIdFormatter.fix_xml_name(
                            ifc_building_element_type.Name or "Unnamed"
                        )
                    )
                )
                opening.appendChild(name)

                # Add CAD object ID
                cad_object_id = self.root.createElement("CADObjectId")
                cad_object_id.appendChild(
                    self.root.createTextNode(
                        XMLIdFormatter.fix_xml_name(
                            ifc_building_element_type.Name or "Unnamed"
                        )
                    )
                )
                opening.appendChild(cad_object_id)

                # Add opening to parent surface
                if (
                    XMLIdFormatter.fix_xml_id(ifc_parent_boundary.GlobalId)
                    in self.dict_id
                ):
                    surface = self.dict_id[
                        XMLIdFormatter.fix_xml_id(ifc_parent_boundary.GlobalId)
                    ]
                    surface.appendChild(opening)

    def build_window_types(self):
        """Build the WindowType elements."""
        ifc_building_element_guids = []

        for ifc_building_element in self.ifc_file.by_type(
            "IfcWindow"
        ) + self.ifc_file.by_type("IfcDoor"):
            ifc_building_element = IFCEntityAnalyzer.get_element_or_type(
                ifc_building_element
            )

            ifc_building_element_guid = ifc_building_element.GlobalId
            if ifc_building_element_guid not in ifc_building_element_guids:
                ifc_building_element_guids.append(ifc_building_element_guid)

                # There doesn't appear to be a 'DoorType' in gbXML
                window_type = self.root.createElement("WindowType")
                window_type.setAttribute(
                    "id", XMLIdFormatter.fix_xml_id(ifc_building_element.GlobalId)
                )
                self.dict_id[
                    XMLIdFormatter.fix_xml_id(ifc_building_element.GlobalId)
                ] = window_type

                # Add name
                name = self.root.createElement("Name")
                name.appendChild(
                    self.root.createTextNode(
                        XMLIdFormatter.fix_xml_name(
                            ifc_building_element.Name or "Unnamed"
                        )
                    )
                )
                window_type.appendChild(name)

                # Add description
                description = self.root.createElement("Description")
                description.appendChild(
                    self.root.createTextNode(
                        XMLIdFormatter.fix_xml_name(
                            ifc_building_element.Name or "Unnamed"
                        )
                    )
                )
                window_type.appendChild(description)

                # Add U-value
                u_value = self.root.createElement("U-value")
                u_value.setAttribute("unit", "WPerSquareMeterK")
                u_value.appendChild(self.root.createTextNode("10.0"))

                pset_u_value = IFCEntityAnalyzer.get_u_value(ifc_building_element)

                if pset_u_value:
                    if self.imperial_units:
                        pset_u_value *= 5.678
                    u_value.firstChild.data = str(pset_u_value)
                    window_type.appendChild(u_value)
                else:
                    print("WARNING: IfcWindow/IfcDoor has no U-value")

                # Add solar heat gain coefficient
                solar_heat_gain_coeff = self.root.createElement("SolarHeatGainCoeff")
                solar_heat_gain_coeff.setAttribute("unit", "Fraction")
                solar_heat_gain_coeff.appendChild(self.root.createTextNode("1.0"))

                pset_solar_heat = IFCEntityAnalyzer.get_solar_heat_gain_coeff(
                    ifc_building_element
                )
                if pset_solar_heat:
                    solar_heat_gain_coeff.firstChild.data = str(pset_solar_heat)
                    window_type.appendChild(solar_heat_gain_coeff)
                else:
                    print(
                        "WARNING: IfcWindow/IfcDoor has no solar heat gain coefficient"
                    )

                # Add transmittance
                transmittance = self.root.createElement("Transmittance")
                transmittance.setAttribute("unit", "Fraction")
                transmittance.setAttribute("type", "Visible")
                transmittance.setAttribute("surfaceType", "Both")
                transmittance.appendChild(self.root.createTextNode("1.0"))

                pset_transmittance = IFCEntityAnalyzer.get_transmittance(
                    ifc_building_element
                )
                if pset_transmittance:
                    transmittance.firstChild.data = str(pset_transmittance)
                    window_type.appendChild(transmittance)
                else:
                    print("WARNING: IfcWindow/IfcDoor has no Transmittance")

                self.gbxml.appendChild(window_type)

    def build_constructions(self):
        """Build the Construction elements."""
        ifc_ids = []
        ifc_material_layer_ids = []

        for ifc_rel_space_boundary in self.ifc_file.by_type("IfcRelSpaceBoundary"):
            # Make sure a 'SpaceBoundary' is representing an actual element
            ifc_building_element = ifc_rel_space_boundary.RelatedBuildingElement
            if ifc_building_element is None:
                continue

            if IFCEntityAnalyzer.get_parent_boundary(ifc_rel_space_boundary):
                continue

            if IFCEntityAnalyzer.is_boundary_element(ifc_building_element):
                ifc_building_element = IFCEntityAnalyzer.get_element_or_type(
                    ifc_building_element
                )
                ifc_material_layer_set = IFCEntityAnalyzer.get_material_layer_set(
                    ifc_building_element
                )

                if ifc_material_layer_set:
                    ifc_id = str(ifc_material_layer_set.id())
                    construction_name = ifc_material_layer_set.LayerSetName or "Unnamed"
                else:
                    # elements without a layer set may have u-value property
                    ifc_id = str(ifc_building_element.id())
                    construction_name = ifc_building_element.Name or "Unnamed"

                # Avoid creating duplicate Construction elements
                if ifc_id not in ifc_ids:
                    ifc_ids.append(ifc_id)
                    self.create_construction_element(
                        ifc_id,
                        construction_name,
                        ifc_building_element,
                        ifc_material_layer_set,
                        ifc_material_layer_ids,
                    )

    def create_construction_element(
        self,
        ifc_id,
        construction_name,
        ifc_building_element,
        ifc_material_layer_set,
        ifc_material_layer_ids,
    ):
        """Create a Construction element."""
        construction = self.root.createElement("Construction")
        construction.setAttribute("id", XMLIdFormatter.fix_xml_construction(ifc_id))
        self.dict_id[XMLIdFormatter.fix_xml_construction(ifc_id)] = construction

        # Add U-value if available
        pset_u_value = IFCEntityAnalyzer.get_u_value(ifc_building_element)
        if pset_u_value:
            # Building Element could have an overall u-value property rather than layers with thicknesses/r-values
            u_value = self.root.createElement("U-value")
            if self.imperial_units:
                pset_u_value *= 5.678
            u_value.setAttribute("unit", "WPerSquareMeterK")
            u_value.appendChild(self.root.createTextNode(str(pset_u_value)))
            construction.appendChild(u_value)

        # Add absorptance if available
        pset_absorptance = IFCEntityAnalyzer.get_absorptance(ifc_building_element)
        if pset_absorptance:
            absorptance = self.root.createElement("Absorptance")
            absorptance.setAttribute("unit", "Fraction")
            absorptance.setAttribute("type", "ExtIR")
            absorptance.appendChild(self.root.createTextNode(str(pset_absorptance)))
            construction.appendChild(absorptance)
        else:
            print("WARNING: Building Element has no Absorptance")

        # Add name
        name = self.root.createElement("Name")
        name.appendChild(self.root.createTextNode(construction_name))
        construction.appendChild(name)

        self.gbxml.appendChild(construction)

        if not ifc_material_layer_set:
            # elements without a layer set may have u-value property
            return

        # Add layer reference
        layer_id = self.root.createElement("LayerId")
        layer_id.setAttribute("layerIdRef", XMLIdFormatter.fix_xml_layer(ifc_id))
        construction.appendChild(layer_id)

        # Create Layer element (collection of materials)
        self.create_layer_element(
            ifc_id, ifc_material_layer_set, ifc_material_layer_ids
        )

    def create_layer_element(
        self, ifc_id, ifc_material_layer_set, ifc_material_layer_ids
    ):
        """Create a Layer element (collection of materials)."""
        # NOTE the 'Layer' element of the gbXML schema is not a layer, it is a
        # collection of layers, ie. a layer set
        layer = self.root.createElement("Layer")
        layer.setAttribute("id", XMLIdFormatter.fix_xml_layer(ifc_id))
        self.dict_id[XMLIdFormatter.fix_xml_layer(ifc_id)] = layer

        # Add material references
        for ifc_material_layer in ifc_material_layer_set.MaterialLayers:
            material_id = self.root.createElement("MaterialId")
            material_id.setAttribute("materialIdRef", f"mat_{ifc_material_layer.id()}")
            layer.appendChild(material_id)
            self.dict_id[f"mat_{ifc_material_layer.id()}"] = layer

        self.gbxml.appendChild(layer)

        # Create Material elements
        for ifc_material_layer in ifc_material_layer_set.MaterialLayers:
            ifc_material = ifc_material_layer.Material
            ifc_material_layer_id = ifc_material_layer.id()

            # Avoid creating duplicate Material elements
            if ifc_material_layer_id not in ifc_material_layer_ids:
                ifc_material_layer_ids.append(ifc_material_layer_id)
                self.create_material_element(
                    ifc_material_layer, ifc_material_layer_id, ifc_material
                )

    def create_material_element(
        self, ifc_material_layer, ifc_material_layer_id, ifc_material
    ):
        """Create a Material element."""
        material = self.root.createElement("Material")
        material.setAttribute("id", f"mat_{ifc_material_layer_id}")
        self.dict_id[f"mat_{ifc_material_layer_id}"] = material

        # Add name
        name = self.root.createElement("Name")
        name.appendChild(self.root.createTextNode(ifc_material.Name or "Unnamed"))
        material.appendChild(name)

        # Add thickness
        thickness = self.root.createElement("Thickness")
        thickness.setAttribute("unit", "Meters")
        layer_thickness = ifc_material_layer.LayerThickness * self.linear_unit_scale
        thickness.appendChild(self.root.createTextNode(str(layer_thickness)))
        material.appendChild(thickness)

        # Add R-value if available
        pset_r_value = IFCEntityAnalyzer.get_r_value(ifc_material)
        pset_u_value = IFCEntityAnalyzer.get_material_u_value(ifc_material)

        if pset_r_value:
            if self.imperial_units:
                pset_r_value /= 5.678
            r_value = self.root.createElement("R-value")
            r_value.setAttribute("unit", "SquareMeterKPerW")
            r_value.appendChild(self.root.createTextNode(str(pset_r_value)))
            material.appendChild(r_value)
        elif pset_u_value:
            r_value = self.root.createElement("R-value")
            r_value.setAttribute("unit", "SquareMeterKPerW")
            r_value.appendChild(
                self.root.createTextNode(str(layer_thickness / pset_u_value))
            )
            material.appendChild(r_value)
        else:
            print("WARNING: IfcMaterial has no R-value")

        self.gbxml.appendChild(material)

    def create_document_history(self):
        """Create the DocumentHistory element."""
        document_history = self.root.createElement("DocumentHistory")

        # Add program info
        program_info = self.root.createElement("ProgramInfo")
        program_info.setAttribute("id", "IFC_gbXML_Convert")
        document_history.appendChild(program_info)

        # Add person info
        person_info = self.root.createElement("PersonInfo")
        person_info.setAttribute(
            "id", XMLIdFormatter.remove_unnecessary_characters(getpass.getuser())
        )
        document_history.appendChild(person_info)

        # Add created by info
        created_by = self.root.createElement("CreatedBy")
        created_by.setAttribute(
            "personId", XMLIdFormatter.remove_unnecessary_characters(getpass.getuser())
        )
        created_by.setAttribute("programId", "IFC_gbXML_Convert")
        today = datetime.date.today()
        created_by.setAttribute(
            "date", today.strftime("%Y-%m-%dT") + time.strftime("%H:%M:%S")
        )
        document_history.appendChild(created_by)

        return document_history

    def build(self):
        """Build the complete gbXML document."""
        self.initialize_document()
        self.build_campus()
        self.build_surfaces()
        self.build_openings()
        self.build_window_types()
        self.build_constructions()
        self.gbxml.appendChild(self.create_document_history())
        return self.root


def create_gbxml(ifc_file):
    """Process an IfcOpenShell file object and return a minidom document in gbXML format."""
    builder = GBXMLBuilder(ifc_file)
    return builder.build()


def main():
    """Entry point for console script."""
    if not len(sys.argv) == 3:
        print("Usage: " + sys.argv[0] + " input.ifc output.xml")
    else:
        path_ifc = sys.argv[1]
        path_xml = sys.argv[2]
        ifc_file = ifcopenshell.open(path_ifc)

        # Create a new XML file and write all created elements to it
        root = create_gbxml(ifc_file)
        root.writexml(open(path_xml, "w"), indent="  ", addindent="  ", newl="\n")


if __name__ == "__main__":
    main()
