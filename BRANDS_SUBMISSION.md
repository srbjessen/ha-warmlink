# Submitting Logo to Home Assistant Brands

To display the WarmLink logo in Home Assistant, submit it to the official brands repository.

## Quick Steps

1. **Fork**: https://github.com/home-assistant/brands

2. **Add files** to `custom_integrations/warmlink/`:
   - `icon.png` (256x256) - from `docs/images/warmlink_logo.png`
   - `icon@2x.png` (512x512) - from `docs/images/warmlink_logo@2x.png`

3. **Create Pull Request**:
   
   **Title**: `Add WarmLink heat pump integration branding`
   
   **Description**:
   ```
   Adding branding for WarmLink custom integration.
   
   WarmLink is a custom integration for Chinese R290 heat pumps using 
   the WarmLink/Linked-Go control platform. It supports multiple brands 
   including Zealux, Alsavo, Aquatemp, Fairland, and Nor-R290.
   
   Integration repository: https://github.com/srbjessen/ha-warmlink
   
   - icon.png (256x256)
   - icon@2x.png (512x512)
   - Meets all brand requirements
   ```

## Why This Is Needed

Home Assistant fetches integration logos from:
```
https://brands.home-assistant.io/{domain}/icon.png
```

Local `icon.png` files are **ignored** by Home Assistant.

## After Submission

1. Wait for PR review (1-7 days)
2. Wait 24-48 hours for Cloudflare cache
3. Clear browser cache
4. Restart Home Assistant
5. Logo appears! ✨

## Logo Requirements ✅

The Amber Waves logo meets all requirements:
- ✅ PNG format
- ✅ 256x256 and 512x512 sizes
- ✅ 1:1 aspect ratio
- ✅ Properly optimized
- ✅ Professional design

The logo files are ready in `docs/images/`!
