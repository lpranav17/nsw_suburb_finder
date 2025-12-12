"use client";

import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix for default marker icon in Next.js
if (typeof window !== "undefined") {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
    iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
    shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  });
}

// Sydney bounds (Greater Sydney area)
const SYDNEY_BOUNDS: L.LatLngBoundsExpression = [
  [-34.2, 150.5], // Southwest
  [-33.6, 151.4], // Northeast
];

const SYDNEY_CENTER: [number, number] = [-33.8688, 151.2093]; // Sydney CBD

interface MapBoundsControllerProps {
  bounds: L.LatLngBoundsExpression;
}

function MapBoundsController({ bounds }: MapBoundsControllerProps) {
  const map = useMap();
  
  useEffect(() => {
    map.setMaxBounds(bounds);
    map.setView(SYDNEY_CENTER, 11);
  }, [map, bounds]);

  return null;
}

interface MapSelectorProps {
  latitude: string;
  longitude: string;
  onLocationSelect: (lat: number, lng: number) => void;
}

export default function MapSelector({ latitude, longitude, onLocationSelect }: MapSelectorProps) {
  const markerRef = useRef<L.Marker>(null);

  const handleMapClick = (e: L.LeafletMouseEvent) => {
    const { lat, lng } = e.latlng;
    // Ensure coordinates are within Sydney bounds
    const bounds = L.latLngBounds(SYDNEY_BOUNDS);
    if (bounds.contains([lat, lng])) {
      onLocationSelect(lat, lng);
    }
  };

  const currentPosition: [number, number] | null = 
    latitude && longitude 
      ? [parseFloat(latitude), parseFloat(longitude)]
      : null;

  return (
    <div style={{ width: "100%", height: "400px", borderRadius: "8px", overflow: "hidden", marginTop: "12px" }}>
      <MapContainer
        center={currentPosition || SYDNEY_CENTER}
        zoom={currentPosition ? 13 : 11}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={true}
        maxBounds={SYDNEY_BOUNDS}
        maxBoundsViscosity={1.0}
      >
        <MapBoundsController bounds={SYDNEY_BOUNDS} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {currentPosition && (
          <Marker
            ref={markerRef}
            position={currentPosition}
            draggable={true}
            eventHandlers={{
              dragend: () => {
                const marker = markerRef.current;
                if (marker) {
                  const position = marker.getLatLng();
                  onLocationSelect(position.lat, position.lng);
                }
              },
            }}
          />
        )}
        <MapClickHandler onMapClick={handleMapClick} />
      </MapContainer>
    </div>
  );
}

interface MapClickHandlerProps {
  onMapClick: (e: L.LeafletMouseEvent) => void;
}

function MapClickHandler({ onMapClick }: MapClickHandlerProps) {
  const map = useMap();

  useEffect(() => {
    map.on("click", onMapClick);
    return () => {
      map.off("click", onMapClick);
    };
  }, [map, onMapClick]);

  return null;
}
